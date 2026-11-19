"""Measure one previously unused, interior waterfall SNR for each PRB/MCS profile."""
import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from calibrate import HERE, aggregate, point_job, run


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--curves", default=HERE / "curves.csv", type=Path)
    cli.add_argument("--output", default=HERE / "validation", type=Path)
    args = cli.parse_args()
    curves = defaultdict(list)
    with args.curves.open() as f:
        for row in csv.DictReader(f):
            curves[int(row["prbs"]), int(row["mcs"])].append((float(row["snr_db"]), float(row["bler"])))
    estimates = {}
    jobs = []
    for (prbs, mcs), rows in sorted(curves.items()):
        rows.sort()
        # Select the fixed neighbouring interval whose midpoint is closest to 50% BLER.
        # New seeds are outside the sweep's seed ranges.
        left, right = min(zip(rows, rows[1:]), key=lambda pair: abs((pair[0][1]+pair[1][1])/2-.5))
        snr = (left[0] + right[0]) / 2
        if snr in dict(rows):
            raise ValueError("Validation SNR must be off-grid")
        estimates[prbs,mcs,snr] = dict(left=left, right=right, predicted_bler=(left[1]+right[1])/2)
        jobs.append(point_job(prbs, mcs, snr, 400, 60000001 + 10000*prbs + 2*mcs))
    raw = args.output / "raw"
    run(jobs, raw, 4)
    expected = {(j["prbs"], j["mcs"], j["snr_db"], j["seed"]):j for j in jobs}
    measurements = aggregate(raw, expected, args.output / "direct.csv")
    checks = []
    for row in measurements:
        pred = estimates[row["prbs"], row["mcs"], row["snr_db"]]
        checks.append(dict(**pred, **row, absolute_error=abs(row["bler"]-pred["predicted_bler"])))
    errors = [r["absolute_error"] for r in checks]
    report = dict(validation_points=len(checks), trials=sum(r["trials"] for r in checks),
                  median_absolute_bler_error=statistics.median(errors), max_absolute_bler_error=max(errors),
                  points=checks)
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"profiles={len(checks)} median_abs={statistics.median(errors):.4f} max_abs={max(errors):.4f}")


if __name__ == "__main__":
    main()
