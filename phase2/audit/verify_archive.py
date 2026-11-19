"""Verify the published OAI curve against original per-seed simulator output."""
import csv
from collections import defaultdict
import gzip
from hashlib import sha256
import io
import json
import math
from pathlib import Path

OAI = Path(__file__).resolve().parents[1] / 'oai'


def key(row):
    return int(row['prbs']), int(row['mcs']), float(row['snr_db'])


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    counts = defaultdict(lambda: [0, 0, 0, 0])
    seeds = set()
    with gzip.open(OAI/'measurements.jsonl.gz','rt') as source:
        for line in source:
            record = json.loads(line)
            require(sha256(record['stdout'].encode()).hexdigest() == record['log_sha256'], 'Damaged stdout')
            native, = csv.DictReader(io.StringIO(record['native_csv']))
            failed_crc, active = map(int, native['n_errors_0'].split('/'))
            planned = int(native['false_positive'].split('/')[1])
            decoded = float(native['eff_rate']) * planned / int(native['TBS'])
            require(abs(decoded-round(decoded)) < .001 and 0 <= round(decoded) <= active <= planned,
                    'Invalid planned/active/decoded counts')
            run_id = key(record), record['seed']
            require(run_id not in seeds and int(record['trials']) == planned, 'Duplicate or incomplete run')
            seeds.add(run_id)
            totals = counts[key(record)]
            for i, value in enumerate((planned, active, round(decoded), failed_crc)):
                totals[i] += value
    with (OAI/'curves.csv').open() as stream:
        table = list(csv.DictReader(stream))
    require(len(table) == len(counts), 'Missing calibration point(s)')
    for row in table:
        planned, active, decoded, crc = counts.pop(key(row))
        require([int(row[k]) for k in ('planned_trials','active_trials','decoded_tbs','reported_errors')]
                == [planned, active, decoded, crc], 'Curve counts differ from native logs')
        require(math.isclose(float(row['bler']), (planned-decoded)/planned, abs_tol=1e-10),
                'Curve loss differs from native logs')
    return dict(verified=True, calibration_points=len(table), seeded_runs=len(seeds),
                trials=sum(int(row['planned_trials']) for row in table),
                curves_sha256=sha256((OAI/'curves.csv').read_bytes()).hexdigest(),
                archive_sha256=sha256((OAI/'measurements.jsonl.gz').read_bytes()).hexdigest())


if __name__ == '__main__':
    print(json.dumps(audit(),indent=2))
