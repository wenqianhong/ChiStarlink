"""Run or re-aggregate calibrated NR PDSCH points through the pinned OAI container."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = "chistarlink-oai:dlsim"
CARRIER_PRBS = 25
MCS = (4, 8, 12, 14, 16, 18, 20, 26)
PRBS = (2, 5, 8, 11)
SNRS = (-20, -14, -10, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 26, 30)
FIELDS = ("prbs", "mcs", "snr_db", "carrier_prbs", "scs_hz", "slot_s", "tbs_bits",
          "errors", "reported_errors", "planned_trials", "active_trials", "decoded_tbs", "active_crc_bler", "trials", "bler", "bler_ci_low", "bler_ci_high")


def point_job(prbs, mcs, snr, trials, seed):
    return dict(prbs=prbs, mcs=mcs, snr_db=snr, trials=trials, seed=seed, carrier_prbs=CARRIER_PRBS)


def run(jobs, output, workers):
    if workers < 1 or any(j["trials"] < 2 for j in jobs):
        raise ValueError("workers >= 1 and trials >= 2 required")
    output.mkdir(parents=True, exist_ok=True)
    # Python -c supplies only the versioned worker program. Its stdin carries JSON.
    command = ["docker", "run", "--rm", "--network", "none", "-i", IMAGE,
               "python3", "-c", (HERE / "worker.py").read_text()]
    with tempfile.TemporaryFile() as jobs_input:
        jobs_input.write(json.dumps(dict(workers=workers, jobs=jobs)).encode())
        jobs_input.seek(0)
        with subprocess.Popen(command, stdin=jobs_input, stdout=subprocess.PIPE, text=True) as sim:
            for line in sim.stdout:
                record = json.loads(line)
                name = f'b{record["prbs"]}_m{record["mcs"]}_s{record["snr_db"]:g}_seed{record["seed"]}.json.gz'
                with (output / name).open("wb") as raw:
                    raw.write(gzip.compress(json.dumps(record).encode(), mtime=0))
            if sim.wait():
                raise RuntimeError("OAI worker exited before completion")


def aggregate(raw, expected, output):
    points = defaultdict(list)
    for path in raw.glob("*.json.gz"):
        item = json.loads(gzip.decompress(path.read_bytes()))
        key = (item["prbs"], item["mcs"], item["snr_db"], item["seed"])
        if key not in expected:
            continue
        if any(item[k] != expected[key][k] for k in expected[key]):
            raise ValueError(f"Job mismatch for {path}")
        if hashlib.sha256(item["stdout"].encode()).hexdigest() != item["log_sha256"]:
            raise ValueError(f"Log checksum mismatch: {path}")
        points[key[:3]].append(item)
    if sum(map(len, points.values())) != len(expected):
        raise ValueError("Sweep incomplete")
    results = []
    for (prbs, mcs, snr), items in sorted(points.items()):
        if len({r["tbs_bits"] for r in items}) != 1:
            raise ValueError("TBS varies within a calibration point")
        count = sum(r["trials"] for r in items)
        errors = sum(r["errors"] for r in items)
        bler = errors/count
        z = 1.95996398454
        den = 1 + z*z/count
        center = (bler + z*z/(2*count))/den
        half = z * math.sqrt(bler*(1-bler)/count + z*z/(4*count*count))/den
        active = sum(r["active_trials"] for r in items)
        reported = sum(r["reported_errors"] for r in items)
        results.append(dict(prbs=prbs, mcs=mcs, snr_db=snr, carrier_prbs=items[0]["carrier_prbs"],
                            scs_hz=15000, slot_s=.001, tbs_bits=items[0]["tbs_bits"], errors=errors,
                            reported_errors=reported, planned_trials=count, active_trials=active, decoded_tbs=count-errors,
                            active_crc_bler=(reported/active if active else None),
                            trials=count, bler=bler, bler_ci_low=max(0.,center-half),
                            bler_ci_high=min(1.,center+half)))
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    # Pack the per-process stdout, unmodified native CSV, invocation and seed
    # together. The unpacked resumable cache stays local.
    records = (json.dumps(r, sort_keys=True) for k in sorted(points)
               for r in sorted(points[k], key=lambda x:x["seed"]))
    with (output.parent / "measurements.jsonl.gz").open("wb") as compressed:
        with gzip.GzipFile(fileobj=compressed, mode="wb", mtime=0) as archive:
            for row in records:
                archive.write(row.encode() + b"\n")
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="mode", required=True)
    single = sub.add_parser("point")
    single.add_argument("--prbs", required=True, type=int)
    single.add_argument("--mcs", required=True, type=int)
    single.add_argument("--snr", required=True, type=float)
    single.add_argument("--trials", default=200, type=int)
    single.add_argument("--seed", required=True, type=int)
    single.add_argument("--output", required=True, type=Path)
    sweep = sub.add_parser("sweep")
    sweep.add_argument("--output", type=Path, default=HERE)
    sweep.add_argument("--workers", type=int, default=4)
    sweep.add_argument("--resume", action="store_true", help="Keep complete prior raw runs")
    args = cli.parse_args()
    if args.mode == "point":
        jobs = [point_job(args.prbs, args.mcs, args.snr, args.trials, args.seed)]
    else:
        jobs = []
        for prbs in PRBS:
            for mcs in MCS:
                for i, snr in enumerate(SNRS):
                    for replica in range(2):
                        seed = 1000001 + prbs*200000 + mcs*2000 + i*4 + replica*2
                        jobs.append(point_job(prbs, mcs, snr, 100, seed))
    def collect(batch):
        todo = batch
        if args.mode == "sweep" and args.resume:
            todo = [j for j in batch if not (raw / f'b{j["prbs"]}_m{j["mcs"]}_s{j["snr_db"]:g}_seed{j["seed"]}.json.gz').is_file()]
        if todo:
            run(todo, raw, getattr(args, "workers", 1))

    raw = args.output / "raw"
    collect(jobs)
    if args.mode == "sweep":
        # Identify steep segments independently for each allocation and MCS.
        # Inspect the broad-grid measurements before drawing the new seeds.
        coarse = defaultdict(lambda: defaultdict(list))
        for j in jobs:
            fname = f'b{j["prbs"]}_m{j["mcs"]}_s{j["snr_db"]:g}_seed{j["seed"]}.json.gz'
            rec = json.loads(gzip.decompress((raw / fname).read_bytes()))
            coarse[(j["prbs"], j["mcs"])][j["snr_db"]].append(rec)
        refinement = []
        for (prbs, mcs), cells in sorted(coarse.items()):
            rates = {snr:sum(v["errors"] for v in records)/sum(v["trials"] for v in records)
                     for snr, records in cells.items()}
            grid = sorted(rates)
            dense = set()
            for idx, (left, right) in enumerate(zip(grid, grid[1:])):
                if abs(rates[right]-rates[left]) > .08:
                    # Include one neighbouring quarter-dB point on either side.
                    start = max(grid[0], left - .25)
                    stop = min(grid[-1], right + .25)
                    dense.update(tick/4 for tick in range(round(4*start), round(4*stop)+1))
            for snr in sorted(dense - set(grid)):
                for replica in range(2):
                    seed = 20000001 + prbs*200000 + mcs*4000 + round((snr+20)*4)*4 + 2*replica
                    refinement.append(point_job(prbs, mcs, snr, 100, seed))
        collect(refinement)
        jobs += refinement
    expected = {(j["prbs"], j["mcs"], j["snr_db"], j["seed"]):j for j in jobs}
    points = aggregate(raw, expected, args.output / "curves.csv")
    print(json.dumps(points[0] if args.mode == "point" else dict(points=len(points), trials=sum(r["trials"] for r in points))))


if __name__ == "__main__":
    main()
