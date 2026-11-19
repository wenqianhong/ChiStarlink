"""Check expected packet-level outcomes for all original repair submissions with the new PHY."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from replay import FIXTURES, run

HERE = Path(__file__).resolve().parent


def main(private, output, publish):
    rows = []
    for task in ("R01", "R02", "R03"):
        for version in ("initial", "reference"):
            submission = FIXTURES / task / "adapter.py" if version == "initial" else private / (task + ".py")
            for case in ("target", "regression", "holdout"):
                dest = output / task / version / case
                result = run(task, case, submission, dest, private / "holdout.json" if case == "holdout" else None)
                expected = version == "reference" or case == "regression"
                matched = result["passed"] if expected else not result["passed"] and not result["checks"]["goodput"]
                row = {
                    "id": task, "version": version, "case": case,
                    "expected_pass": expected, "passed": result["passed"], "matched": matched,
                    "judgment_sha256": hashlib.sha256((dest/"judgment.json").read_bytes()).hexdigest(),
                    "measured_curve_sha256": result["oai_sha256"],
                }
                if case != "holdout":
                    row.update(result["network"])
                    row.update(result["first_sample"])
                rows.append(row)
                if publish and case == "target":
                    folder = HERE / "evidence" / "target" / task / version
                    folder.mkdir(parents=True, exist_ok=True)
                    for name in ("layers.csv","trace.csv","metrics.json","judgment.json"):
                        shutil.copy2(dest / name, folder / name)
    if len({r["measured_curve_sha256"] for r in rows}) != 1:
        raise RuntimeError("Waveform calibration changed during the replay")
    summary = {"matched": sum(r["matched"] for r in rows), "total": len(rows), "matrix": rows}
    text = json.dumps(summary, indent=2) + "\n"
    (output/"summary.json").write_text(text)
    if publish:
        (HERE/"evidence/summary.json").write_text(text)
    print(f'{summary["matched"]}/{summary["total"]} expected outcomes')
    return int(summary["matched"] != summary["total"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private", type=Path, default=FIXTURES/".private")
    p.add_argument("--output", type=Path, default=HERE/".private/full")
    p.add_argument("--publish-evidence", action="store_true", help="Copy only aggregate results and public target logs")
    args = p.parse_args()
    raise SystemExit(main(args.private,args.output,args.publish_evidence))
