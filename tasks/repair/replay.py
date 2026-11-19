"""Judge a submitted adapter through geometry, RF, modem, and native ns-3 UDP replay."""
import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RADIO_IMAGE = "chistarlink-repair:phase1"


def assess(task, case, adapter, output, holdout=None):
    config = json.loads((ROOT / "scenario.json").read_text())
    site = json.loads(holdout.read_text()) if holdout else config["cases"][case]
    output.mkdir(parents=True, exist_ok=True)
    # Mount only the current case, adapter and scratch output in the radio container.
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for source in ("trace.py", "scenario.json"):
            shutil.copy2(ROOT / source, stage / source)
        shutil.copy2(adapter, stage / "submission.py")
        command = [
            "docker", "run", "--rm", "--network", "none", "-v", f"{stage}:/work", RADIO_IMAGE,
            "python", "trace.py", task, case, "--adapter", "submission.py", "--output", "out",
        ]
        if holdout:
            shutil.copy2(holdout, stage / "holdout.json")
            command.extend(["--holdout", "holdout.json"])
        subprocess.run(command, check=True)
        for filename in ("trace.csv", "layers.csv"):
            shutil.copy2(stage / "out" / filename, output / filename)
    network = ROOT.parent / "regression" / "network.py"
    command = [sys.executable, str(network), "--trace", str(output / "trace.csv"),
               "--offered-mbps", str(config["offered_mbps"]), "--duration-s", str(config["duration_s"]),
               "--output", str(output)]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    app = json.loads((output / "metrics.json").read_text())
    with (output / "layers.csv").open() as f:
        layers = list(csv.DictReader(f))
    with (output / "trace.csv").open() as f:
        trace = list(csv.DictReader(f))
    # Friis in linear power units is independent of the native dB-domain RF calculation.
    # The acceptance fixture specifies a co-polarized pair, including the short-label profiles.
    antenna_factor = 10 ** ((config["tx_gain_dbi"] + config["rx_gain_dbi"] - config["tx_losses_db"]) / 10)
    noise_density = 1.380649e-23 * config["noise_temp_k"]
    wavelength = 299792458 / config["carrier_hz"]
    def expected_cn0(range_m):
        received_w = config["tx_power_w"] * antenna_factor * (wavelength / (4 * math.pi * range_m)) ** 2
        return 10 * math.log10(received_w / noise_density)

    checks = {
        "trace_complete": len(layers) == len(trace) == app["sample_count"] == config["duration_s"],
        "angle_decoded": all(abs(float(r["true_elev_deg"]) - float(r["access_input_deg"])) < 1e-8 for r in layers),
        "rf_power_oracle": all(abs(float(r["cn0_dbhz"]) - expected_cn0(float(r["range_m"]))) < 0.02
                               for r in layers),
        "polarization": all(r["rx_pol"] == site.get("polarization", "RHCP") for r in layers),
        "rate_mapping": all(abs(1e6 * float(r["capacity_mbps"]) - float(t["rate_bps"])) <= 0.5
                            for r, t in zip(layers, trace)),
        "propagation": all(math.isclose(float(r["range_m"]) / 299792458, float(t["delay_s"]))
                           for r, t in zip(layers, trace)),
        "sent": app["sent_packets"] > 0,
        "delivery": app["delivery_ratio"] >= 0.99,
        "goodput": app["payload_mbps"] >= 0.99,
        "latency": app["p95_delay_ms"] is not None and app["p95_delay_ms"] <= 15.0,
    }
    result = {
        "id": task, "case": case, "passed": all(checks.values()), "checks": checks,
        "range_at_start_m": float(layers[0]["range_m"]),
        "ebn0_at_start_db": float(layers[0]["ebn0_db"]),
        "service_rate_at_start_bps": int(trace[0]["rate_bps"]), "network": app,
    }
    (output / "judgment.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("task", choices=["R01", "R02", "R03"])
    p.add_argument("--case", choices=["target", "regression", "holdout"], default="target")
    p.add_argument("--adapter", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--holdout", type=Path)
    args = p.parse_args()
    if (args.case == "holdout") != bool(args.holdout):
        p.error("Provide --holdout only with --case holdout")
    result = assess(args.task, args.case, args.adapter or ROOT / args.task / "adapter.py",
                    args.output.resolve(), args.holdout)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)
