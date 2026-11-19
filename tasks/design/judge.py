"""Run the full directional service-link design evaluation in two Docker images."""
import argparse
import csv
import json
import math
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CASES = json.loads((HERE / "tasks.json").read_text())["cases"]
RADIO_IMAGE = "chistarlink-repair:phase1"


def judge(case_id, output, candidate=None, profile="target", start_offset_s=0):
    case = CASES[case_id]
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    offset = -30 if profile == "regression" else start_offset_s
    offered = 0.15 if profile == "regression" else case["offered_mbps"]
    min_payload = 0.14 if profile == "regression" else case["min_payload_mbps"]
    # Staging only the task inputs also keeps reference/holdout files out of the container.
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        for name in ("tasks.json", "replay.py", "radio.py"):
            shutil.copyfile(HERE / name, work / name)
        args = ["python", "/work/replay.py", case_id, "--output", "/work/out",
                "--start-offset-s", str(offset)]
        if candidate:
            shutil.copyfile(candidate, work / "candidate.json")
            args.extend(["--candidate", "/work/candidate.json"])
        container = subprocess.check_output(
            ["docker", "create", "--network", "none", RADIO_IMAGE, *args], text=True
        ).strip()
        try:
            subprocess.run(["docker", "cp", f"{work}/.", f"{container}:/work"], check=True)
            subprocess.run(["docker", "start", "-a", container], check=True)
            subprocess.run(["docker", "cp", f"{container}:/work/out/.", str(output)], check=True)
        finally:
            subprocess.run(["docker", "rm", "-f", container], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(ROOT / "tasks/regression/network.py"),
                    "--trace", str(output / "trace.csv"), "--offered-mbps", str(offered),
                    "--duration-s", str(case["duration_s"]), "--output", str(output)], check=True)
    metrics = json.loads((output / "metrics.json").read_text())
    with (output / "radio.csv").open() as source:
        rows = list(csv.DictReader(source))
    checks = {
        "sample_count": len(rows) == case["duration_s"] == metrics["sample_count"],
        "propagation_delay": all(math.isclose(float(r["range_m"]) / 299792458, float(r["delay_s"])) for r in rows),
        "delivery": metrics["delivery_ratio"] >= case["min_delivery"],
        "payload": metrics["payload_mbps"] >= min_payload,
        "latency": metrics["p95_delay_ms"] is not None and metrics["p95_delay_ms"] <= case["max_p95_ms"],
    }
    result = {"id": case_id, "profile": profile, "passed": all(checks.values()),
              "checks": checks, "network": metrics}
    (output / "judgment.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("case", choices=list(CASES))
    p.add_argument("--candidate", type=Path)
    p.add_argument("--profile", choices=["target","regression"], default="target")
    p.add_argument("--start-offset-s", type=int, default=0)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = judge(args.case, args.output, args.candidate, args.profile, args.start_offset_s)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)
