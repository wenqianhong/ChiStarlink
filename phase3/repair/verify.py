"""Accept a task only when six runs agree, including an observable network failure on the broken target."""

import argparse
import json
from pathlib import Path
from replay import HERE, SPECS, job, run


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private", type=Path, default=HERE / ".private")
    p.add_argument("--output", type=Path, default=HERE / ".private/full")
    p.add_argument("--ids", nargs="+", choices=sorted(SPECS))
    p.add_argument("--workers", type=int, default=2)
    args = p.parse_args()
    jobs = []
    for task in args.ids or sorted(SPECS):
        for version, adapter in (
            ("initial", HERE / "input" / task / "adapter.py"),
            ("reference", args.private / "reference" / (task + ".py")),
        ):
            for case in ("target", "regression", "holdout"):
                jobs.append(
                    job(task, case, adapter, version, args.private / "holdout.json")
                )
    results = run(jobs, args.output, args.workers)
    for r in results:
        expected = r["version"] == "reference" or r["case"] == "regression"
        r["expected_pass"] = expected
        healthy = all(r["checks"][k] for k in ("throughput", "delivery", "latency"))
        r["matched"] = r["passed"] == expected and (expected or not healthy)
    output = {
        "matched": sum(r["matched"] for r in results),
        "count": len(results),
        "rows": results,
    }
    (args.output / "summary.json").write_text(json.dumps(output, indent=2) + "\n")
    for r in results:
        if not r["matched"]:
            print(r["id"], r["version"], r["case"], r["checks"], r["metrics"])
    print(f"{output['matched']}/{output['count']} outcomes matched")
    return int(output["matched"] != output["count"])


if __name__ == "__main__":
    raise SystemExit(main())
