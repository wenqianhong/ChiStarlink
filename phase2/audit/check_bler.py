"""Direct OAI decode at two actual C02 SNRs and an ungridded transition point."""
import argparse
from bisect import bisect_left
import csv
import json
from pathlib import Path
import subprocess
import sys

PHASE = Path(__file__).resolve().parents[1]


def interpolate(rows, snr):
    axis = [float(row['snr_db']) for row in rows]
    if not axis[0] <= snr <= axis[-1]:
        raise ValueError('Audit SNR outside measured calibration range')
    ix = bisect_left(axis, snr)
    if axis[ix] == snr:
        return float(rows[ix]['bler'])
    fraction = (snr-axis[ix-1])/(axis[ix]-axis[ix-1])
    return (1-fraction)*float(rows[ix-1]['bler']) + fraction*float(rows[ix]['bler'])


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--profiles', required=True, type=Path, help='C02 first-epoch public operating points')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    with (PHASE/'oai/curves.csv').open() as stream:
        curves = list(csv.DictReader(stream))
    jobs = json.loads(args.profiles.read_text())
    points = []
    for index, job in enumerate(jobs):
        prbs, mcs = job['prbs'], job['mcs']
        grid = sorted((r for r in curves if int(r['prbs']) == prbs and int(r['mcs']) == mcs),
                      key=lambda row: float(row['snr_db']))
        if job.get('transition'):
            # The midpoint of the largest observed BLER change in this profile.
            left, right = max(zip(grid, grid[1:]),key=lambda pair:float(pair[0]['bler'])-float(pair[1]['bler']))
            snr = (float(left['snr_db'])+float(right['snr_db']))/2
        else:
            snr = round(job['snr_db'], 3)
        predicted = interpolate(grid, snr)
        dest = args.output/job['case']
        subprocess.run([sys.executable,str(PHASE/'oai/calibrate.py'),'point','--prbs',str(prbs),
                        '--mcs',str(mcs),'--snr',str(snr),'--trials','400','--seed',str(823481+2*index),
                        '--output',str(dest)],check=True)
        with (dest/'curves.csv').open() as stream:
            measured, = csv.DictReader(stream)
        direct = float(measured['bler'])
        points.append(dict(case=job['case'],prbs=prbs,mcs=mcs,snr_db=snr,
                           interpolated_bler=predicted,direct_bler=direct,
                           absolute_gap=abs(direct-predicted),trials=int(measured['trials']),
                           errors=int(measured['errors']),wilson95=[float(measured['bler_ci_low']),
                                                                   float(measured['bler_ci_high'])]))
    (args.output/'summary.json').write_text(json.dumps(points,indent=2)+'\n')


if __name__ == '__main__':
    main()
