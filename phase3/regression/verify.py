"""Run the full two-window acceptance matrix, retaining all attempted outcomes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import tempfile
from pathlib import Path

from replay import HERE, ROOT, TASKS, load_fixture, run


def verify(task, fixture, answers, output):
    results = []
    for group, window in (('main', task['main']), ('secondary', answers['secondary'])):
        for label, candidate in (('initial', {}), ('reference', answers['reference'])):
            for demand in ('old','new'):
                stage = f'{group}-{label}-{demand}'
                result = run(fixture, task, demand, candidate, window, output/task['id']/stage)
                expected = (label, demand) != ('initial','new')
                results.append({'stage':stage, 'expected':expected, **result})
    verified = all(row['passed']==row['expected'] for row in results)
    item = dict(id=task['id'], verified=verified, runs=results)
    (output/f'{task["id"]}.json').write_text(json.dumps(item, indent=2)+'\n')
    print(task['id'], 'ACCEPT' if verified else 'FILTER',
          [(r['stage'], round(r['metrics']['payload_mbps'], 3), r['metrics']['p95_delay_ms'])
           for r in results if r['passed'] != r['expected']], flush=True)
    return item


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--controls', type=Path, default=HERE/'private/controls.json')
    cli.add_argument('--output', type=Path, default=HERE/'private/runs')
    cli.add_argument('--tasks', nargs='+',default=list(TASKS),choices=list(TASKS))
    cli.add_argument('--jobs', type=int, default=2)
    args = cli.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    controls = json.loads(args.controls.read_text())
    def fingerprint(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = dict(curves_sha256=fingerprint(ROOT/'phase2/oai/curves.csv'),
                    tasks_sha256=fingerprint(HERE/'tasks.json'), controls_sha256=fingerprint(args.controls))
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    with tempfile.TemporaryDirectory() as tmp:
        fixture = load_fixture(Path(tmp))
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            records = list(pool.map(lambda cid: verify(TASKS[cid],fixture,controls[cid],args.output),args.tasks))
    if not all(r['verified'] for r in records):
        raise SystemExit('Some proposed tasks failed matrix screening')
