"""Evaluate new regression tasks on the phase-two radio chain and native Hypatia network."""
import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from phase2.cases.replay import configure_link, load_fixture
from tasks.regression import replay as hypatia

TASKS = {r['id']: r for r in json.loads((HERE / 'tasks.json').read_text())}


def run(fixture, spec, condition, candidate, window, output=None):
    if not isinstance(candidate, dict) or set(candidate) - set(spec['editable']):
        raise ValueError('Candidate contains fields outside the task edit scope')
    if not all(type(value) in (int, float) and math.isfinite(value) and value > 0 for value in candidate.values()):
        raise ValueError('Supply positive, finite engineering values')
    demand = spec[condition]
    radio = {**spec['initial'], **candidate, **demand['radio']}
    share = radio.pop('dl_fraction', 1.)
    radio['noise_k'] = radio.get('noise_k', 290.) + window['noise_offset_k']
    start, duration = window['start_s'], window['duration_s']
    end = round((start + duration + .5) * 1e9)
    with tempfile.TemporaryDirectory() as tmp:
        working = Path(tmp) / 'case'
        shutil.copytree(fixture, working, ignore=shutil.ignore_patterns(hypatia.ROUTES, 'logs_ns3'))
        network = working / 'satellite_network_state'
        dynamic = network / hypatia.ROUTES
        dynamic.mkdir()
        for time in range(0, end, hypatia.INTERVAL_NS):
            for prefix in ('fstate', 'gsl_if_bandwidth'):
                name = f'{prefix}_{time}.txt'
                shutil.copyfile(fixture / 'satellite_network_state' / hypatia.ROUTES / name, dynamic / name)
        cfg = working / 'run/config_ns3.properties'
        cfg.write_text(cfg.read_text().replace('200000000000\n', f'{end}\n'))
        (working / 'run/udp_burst_schedule.csv').write_text(
            f'0,17,18,{demand["offered_mbps"]},{round(start*1e9)},{round(duration*1e9)},,\n')
        trace = configure_link(network, radio, end, dl_share=share)
        for sample in trace:
            sample['full_downlink_bps'] = sample.get('full_downlink_rate_bps', sample['rate_bps'])
            sample['dl_fraction'] = share
            # Hypatia applies the last assignment for a transmitting interface.
            # Coalesce native assignments and verify the actual simulation input.
            if sample['rate_bps']:
                time_ns = round(sample['time_s'] * 1e9)
                path = dynamic / f'gsl_if_bandwidth_{time_ns}.txt'
                assignments = {(node, iface): value for node, iface, value in hypatia.rows(path)}
                key = (str(sample['sat_id']), str(sample['hop'][1]))
                native_bps = round(float(assignments[key]) * hypatia.GSL_MBPS * 1e6)
                if native_bps != min(sample['rate_bps'], hypatia.GSL_MBPS * 1e6):
                    raise ValueError(f'Downlink mismatch at {time_ns}: {native_bps} bps')
                path.write_text(''.join(f'{node},{iface},{value}\n'
                                        for (node, iface), value in assignments.items()))
                sample['native_tx_bps'] = native_bps
        metrics = hypatia.execute(working)
        raw = ('\n'.join(json.dumps(x, sort_keys=True) for x in trace)+'\n').encode()
        if output:
            output.mkdir(parents=True, exist_ok=True)
            (output/'radio.jsonl').write_bytes(raw)
            for path in (working/'run/logs_ns3').glob('udp*.csv'):
                shutil.copy(path, output/path.name)
    limits = demand['limits']
    checks = {'payload': metrics['payload_mbps'] >= demand['min_payload_mbps'],
              'delivery': metrics['delivery_ratio'] >= demand['min_delivery'],
              'delay': metrics['p95_delay_ms'] is not None and metrics['p95_delay_ms'] <= demand['max_p95_ms'],
              'power': radio['tx_w'] <= limits['max_tx_w'],
              'spectrum': radio['bandwidth_hz'] <= limits['max_bandwidth_hz'],
              'aperture': radio['rx_diameter_m'] <= limits['max_rx_diameter_m']}
    metrics = {k: v for k,v in metrics.items() if k not in ('incoming_csv','outgoing_csv')}
    result = dict(passed=all(checks.values()), checks=checks, metrics=metrics,
                  samples=len(trace), radio_sha256=hashlib.sha256(raw).hexdigest(),
                  service_rate_range_bps=[min(r['rate_bps'] for r in trace), max(r['rate_bps'] for r in trace)])
    if output:
        (output/'judgment.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('task', choices=list(TASKS))
    cli.add_argument('--condition', required=True, choices=['old','new'])
    cli.add_argument('--candidate', type=Path, help='JSON object containing permitted engineering edits')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    spec = TASKS[args.task]
    cand = json.loads(args.candidate.read_text()) if args.candidate else {}
    with tempfile.TemporaryDirectory() as tmp:
        outcome = run(load_fixture(Path(tmp)), spec, args.condition, cand, spec['main'], args.output)
    print(json.dumps(outcome))
    sys.exit(0 if outcome['passed'] else 1)
