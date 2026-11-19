"""Replay one public or locally retained adapter through two isolated simulator containers."""

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from tasks.regression.network import replay as network_replay

SPECS = {x["id"]: x for x in json.loads((HERE / "specs.json").read_text())}
SCENES = json.loads((HERE / "scenes.json").read_text())
CURVE = ROOT / "phase2/oai/curves.csv"
IMAGE = "chistarlink-itur:phase2"


def job(task, case, adapter, version, hidden=None):
    return {
        "spec": SPECS[task],
        "case": case,
        "adapter": Path(adapter),
        "scene": json.loads(hidden.read_text()) if case == "holdout" else SCENES[case],
        "key": f"{task}/{version}/{case}",
        "version": version,
        "duration_s": SCENES["duration_s"],
    }


def make_traces(jobs, dest):
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        staged = []
        for item in jobs:
            task = item["spec"]["id"]
            decoder = f"{task}-{item['version']}.py"
            encoder = f"{task}-source.py"
            shutil.copy2(item["adapter"], stage / decoder)
            shutil.copy2(HERE / "input" / task / "source.py", stage / encoder)
            staged.append(
                {
                    **{k: v for k, v in item.items() if k != "adapter"},
                    "decoder": decoder,
                    "encoder": encoder,
                }
            )
        (stage / "jobs.json").write_text(json.dumps(staged))
        shutil.copy2(ROOT / "tasks/repair/scenario.json", stage / "base.json")
        mounts = ["-v", f"{stage}:/job"]
        for p in (
            "phase3/repair/radio.py",
            "phase2/cases/nr.py",
            "phase2/oai/curves.csv",
            "phase2/propagation/gas.py",
        ):
            mounts.extend(["-v", f"{ROOT / p}:/repo/{p}:ro"])
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                *mounts,
                "-w",
                "/repo",
                IMAGE,
                "python",
                "-m",
                "phase3.repair.radio",
            ],
            check=True,
        )
        shutil.copytree(stage / "out", dest, dirs_exist_ok=True)


def judge(item, output, curve_digest):
    spec = item["spec"]
    data = output / item["key"]
    app = network_replay(
        data / "trace.csv", spec["offered_mbps"], SCENES["duration_s"], data
    )
    with (data / "layers.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    with (data / "trace.csv").open() as stream:
        traces = list(csv.DictReader(stream))
    checks = {
        "interface_contract": all(int(r["contract_ok"]) for r in rows),
        "nr_bracket": all(
            float(r["lower_snr_db"]) <= float(r["snr_db"]) <= float(r["upper_snr_db"])
            and float(r["occupied_bw_hz"]) <= float(r["bandwidth_hz"])
            for r in rows
        ),
        "gas_applied_once": all(
            math.isclose(
                float(r["vacuum_cn0_dbhz"]) - float(r["gas_db"]), float(r["cn0_dbhz"])
            )
            for r in rows
        ),
        "device_input": len(rows) == len(traces) == app["sample_count"]
        and all(
            int(r["network_bps"]) == int(t["rate_bps"])
            and math.isclose(float(r["delay_s"]), float(t["delay_s"]))
            for r, t in zip(rows, traces)
        ),
        "throughput": app["payload_mbps"] >= 0.98 * spec["offered_mbps"],
        "delivery": app["sent_packets"] > 0 and app["delivery_ratio"] >= 0.98,
        "latency": app["p95_delay_ms"] is not None
        and app["p95_delay_ms"] <= spec["max_p95_ms"],
    }
    result = {
        "id": spec["id"],
        "version": item["version"],
        "case": item["case"],
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": app,
        "curve_sha256": curve_digest,
        "adapter_sha256": hashlib.sha256(item["adapter"].read_bytes()).hexdigest(),
        "layers_sha256": hashlib.sha256((data / "layers.csv").read_bytes()).hexdigest(),
        "trace_sha256": hashlib.sha256((data / "trace.csv").read_bytes()).hexdigest(),
    }
    (data / "judgment.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def run(jobs, output, workers=1):
    curve_digest = hashlib.sha256(CURVE.read_bytes()).hexdigest()
    make_traces(jobs, output)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda item: judge(item, output, curve_digest), jobs))
    if hashlib.sha256(CURVE.read_bytes()).hexdigest() != curve_digest:
        raise RuntimeError("Calibration changed during replay")
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("id", choices=sorted(SPECS))
    p.add_argument(
        "--case", choices=("target", "regression", "holdout"), default="target"
    )
    p.add_argument("--adapter", type=Path)
    p.add_argument("--holdout", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if bool(args.holdout) != (args.case == "holdout"):
        p.error("--holdout is required only for a retained input")
    entry = job(
        args.id,
        args.case,
        args.adapter or HERE / "input" / args.id / "adapter.py",
        "submitted",
        args.holdout,
    )
    result = run([entry], args.output)[0]
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(int(not result["passed"]))
