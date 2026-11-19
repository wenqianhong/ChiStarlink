"""Cross-check the first healthy R03 operating point with independent OAI noise trials."""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OAI = HERE.parent / "oai"


def read_csv(path):
    with path.open() as src:
        return list(csv.DictReader(src))


def main(output, precision, seed):
    first = read_csv(HERE / "evidence/target/R03/reference/layers.csv")[0]
    prbs = int(first["prbs"])
    mcs = int(first["mcs"])
    snr = round(float(first["snr_db"]), precision)
    points = sorted((row for row in read_csv(OAI/"curves.csv") if
                     int(row["prbs"]) == prbs and int(row["mcs"]) == mcs),
                    key=lambda row: float(row["snr_db"]))
    low = max((pt for pt in points if float(pt["snr_db"]) < snr),key=lambda pt:float(pt["snr_db"]))
    high = min((pt for pt in points if float(pt["snr_db"]) > snr),key=lambda pt:float(pt["snr_db"]))
    if any(float(pt["snr_db"]) == snr for pt in points):
        raise ValueError("The independent probe must use an off-grid SNR")
    weight = (snr-float(low["snr_db"])) / (float(high["snr_db"])-float(low["snr_db"]))
    def interpolate(field):
        return (1-weight)*float(low[field]) + weight*float(high[field])
    cmd = [sys.executable,str(OAI/"calibrate.py"),"point","--prbs",str(prbs),"--mcs",str(mcs),
           "--snr",str(snr),"--seed",str(seed),"--trials","300","--output",str(output)]
    subprocess.run(cmd,check=True)
    direct = read_csv(output/"curves.csv")[0]
    # Compare the independent Wilson interval with linearly interpolated endpoint Wilson bounds.
    # This diagnostic describes agreement with the tabulation and does not certify calibrated coverage.
    lower, upper = interpolate("bler_ci_low"), interpolate("bler_ci_high")
    observed_pair = [float(direct["bler_ci_low"]),float(direct["bler_ci_high"])]
    overlap = max(observed_pair[0],lower) <= min(observed_pair[1],upper)
    result = {"task":"R03","case":"target/reference","sample_time_s":0,
              "actual_snr_db":float(first["snr_db"]),"probe_snr_db":snr,"mcs":mcs,"prbs":prbs,
              "seed":seed,"trials":int(direct["trials"]),"errors":int(direct["errors"]),
              "interpolated_bler":interpolate("bler"),"direct_bler":float(direct["bler"]),
              "direct_wilson_95":observed_pair,"interpolated_endpoint_wilson_bounds":[lower,upper],
              "intervals_overlap":overlap}
    (output/"comparison.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return int(not overlap)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=HERE/"evidence/offgrid")
    p.add_argument("--precision", type=int, choices=[1, 2], default=2)
    p.add_argument("--seed", type=int, default=8439917)
    args = p.parse_args()
    raise SystemExit(main(args.output, args.precision, args.seed))
