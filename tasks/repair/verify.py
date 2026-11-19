"""Run and check all six outcomes per repair task using a local evaluator directory."""
import argparse
import hashlib
import json
from pathlib import Path

from replay import ROOT, assess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private", type=Path, required=True, help="Directory containing R01.py–R03.py and holdout.json")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    audit = []
    for task in ["R01", "R02", "R03"]:
        for version in ["initial", "reference"]:
            adapter = ROOT / task / "adapter.py" if version == "initial" else args.private / f"{task}.py"
            for case in ["target", "regression", "holdout"]:
                dst = output / task / version / case
                result = assess(task, case, adapter, dst,
                                args.private / "holdout.json" if case == "holdout" else None)
                expected = version == "reference" or case == "regression"
                # Broken on-port scenarios must regress application goodput, not merely metadata.
                observed = result["passed"] if expected else (
                    not result["passed"] and not result["checks"]["goodput"]
                )
                audit.append({"id":task, "version":version, "case":case, "expected_pass":expected,
                              "passed":result["passed"], "matched":observed,
                              "sent":result["network"]["sent_packets"],
                              "received":result["network"]["received_packets"],
                              "payload_mbps":result["network"]["payload_mbps"],
                              "p95_delay_ms":result["network"]["p95_delay_ms"],
                              "judgment_sha256":hashlib.sha256((dst / "judgment.json").read_bytes()).hexdigest()})
    (output / "summary.json").write_text(json.dumps(audit, indent=2) + "\n")
    matched = sum(row["matched"] for row in audit)
    print(f"{matched}/{len(audit)} outcomes matched.")
    return 0 if matched == len(audit) else 1


if __name__ == "__main__":
    raise SystemExit(main())
