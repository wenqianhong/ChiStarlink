"""Replay a directional sampled service capacity in ns-3.31. Uses a local Docker image."""
import argparse
import csv
import json
import math
import subprocess
from pathlib import Path

IMAGE = "chistarlink-hypatia:0ac531c"
SERVICE = "build/optimized/scratch/service-link"


def replay(trace, offered_mbps, duration_s, output):
    if not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("duration_s must be positive and finite")
    if not math.isfinite(offered_mbps) or not 0 < offered_mbps < 8000:
        raise ValueError("offered_mbps must be positive and below 8000 Mbps")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    link_id = None
    with Path(trace).open() as source:
        for row in csv.DictReader(source):
            time, rate, delay = [float(row[k]) for k in ("time_s", "rate_bps", "delay_s")]
            if not all(math.isfinite(v) and v >= 0 for v in (time, rate, delay)):
                raise ValueError(f"Invalid sample: {row}")
            if rows and time <= rows[-1][0]:
                raise ValueError("Sample times must increase")
            if link_id is not None and row["link_id"] != link_id:
                raise ValueError("Supply a single directional link per trace")
            link_id = row["link_id"]
            rows.append((time, round(rate), delay))
    if not rows or rows[0][0] != 0:
        raise ValueError("First sample must start at t=0")
    samples = "".join(f"{t} {rate} {delay}\n" for t, rate, delay in rows if t < duration_s)
    result = subprocess.run([
        "docker", "run", "--rm", "--network", "none", "-i", IMAGE, SERVICE,
        "--input=/dev/stdin", "--output=/dev/stdout",
        f"--duration={duration_s}", f"--offered={offered_mbps}"
    ], input=samples, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    metrics = json.loads(result.stdout)
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    return metrics


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--trace", required=True, type=Path)
    cli.add_argument("--offered-mbps", required=True, type=float)
    cli.add_argument("--duration-s", required=True, type=float)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    print(json.dumps(replay(args.trace, args.offered_mbps, args.duration_s, args.output)))
