"""Run the unchanged failure, normal and retained variants with the phase-two PHY."""
import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tasks/repair"
IMAGE = "chistarlink-itur:phase2"


def run(task, case, adapter, output, holdout=None):
    cfg = json.loads((FIXTURES / "scenario.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copy2(adapter, stage / "submission.py")
        mounts = ["-v", f"{stage}:/job"]
        # Mount only the runtime and active submission. The benchmark reference store stays on the host.
        for path in ("phase2/repair/trace.py", "phase2/cases/nr.py", "phase2/propagation/gas.py",
                     "phase2/oai/curves.csv", "tasks/repair/scenario.json", "tasks/repair/trace.py"):
            mounts.extend(["-v", f"{ROOT/path}:/repo/{path}:ro"])
        cmd = ["docker", "run", "--rm", "--network", "none", *mounts, "-w", "/repo", IMAGE,
               "python", "-m", "phase2.repair.trace", task, case,
               "--adapter", "/job/submission.py", "--output", "/job/out"]
        if holdout:
            shutil.copy2(holdout, stage / "scene.json")
            cmd.extend(["--holdout", "/job/scene.json"])
        subprocess.run(cmd, check=True)
        for name in ("layers.csv","trace.csv"):
            shutil.copy2(stage / "out" / name, output / name)
    network = ROOT / "tasks/regression/network.py"
    subprocess.run([sys.executable, str(network), "--trace", str(output / "trace.csv"),
                    "--offered-mbps", str(cfg["offered_mbps"]), "--duration-s", str(cfg["duration_s"]),
                    "--output", str(output)], check=True, stdout=subprocess.DEVNULL)
    app = json.loads((output / "metrics.json").read_text())
    with (output / "layers.csv").open() as f:
        rows = list(csv.DictReader(f))
    with (output / "trace.csv").open() as f:
        trace = list(csv.DictReader(f))
    raw_curves = ROOT / "phase2/oai/curves.csv"
    curve_sha = hashlib.sha256(raw_curves.read_bytes()).hexdigest()
    with raw_curves.open() as f:
        points = {(int(v["prbs"]), int(v["mcs"]), float(v["snr_db"])): v for v in csv.DictReader(f)}
    def physical_rows(r):
        cn0 = float(r["postgas_cn0_dbhz"])
        occupied = int(r["prbs"]) * int(r["scs_hz"]) * 12
        snr = cn0 - 10 * math.log10(occupied)
        bracket = []
        for side in ("lower","upper"):
            edge = float(r[side + "_snr_db"])
            point = points[int(r["prbs"]),int(r["mcs"]),edge]
            if any(int(point[key]) != int(r[side+"_"+key]) for key in ("errors","trials")):
                return False
            if int(point["tbs_bits"]) != int(r["tbs_bits"]) or float(point["slot_s"]) != float(r["slot_s"]):
                return False
            bracket.append((edge, int(point["errors"]) / int(point["trials"])))
        (lo, el), (hi, eh) = bracket
        if not lo <= snr <= hi or occupied > float(r["allocation_limit_hz"]):
            return False
        bler = el if hi == lo else el + (eh-el) * (snr-lo)/(hi-lo)
        goodput = round(int(r["tbs_bits"]) / float(r["slot_s"]) * (1-bler))
        return (math.isclose(float(r["snr_db"]), snr, abs_tol=1e-8) and
                math.isclose(float(r["bler"]), bler, abs_tol=1e-8) and goodput == int(r["rate_bps"]))

    # Independent linear Friis budget for the specified, co-polarized terminal pair.
    gain = 10 ** ((cfg["tx_gain_dbi"] + cfg["rx_gain_dbi"] - cfg["tx_losses_db"]) / 10)
    def vacuum_cn0(range_m):
        received_w = cfg["tx_power_w"] * gain * (299792458 / (cfg["carrier_hz"] * 4 * math.pi * range_m))**2
        return 10 * math.log10(received_w / (1.380649e-23 * cfg["noise_temp_k"]))

    checks = {
        "sample_count": len(rows) == len(trace) == app["sample_count"] == cfg["duration_s"],
        "independent_vacuum_budget": all(abs(float(r["vacuum_cn0_dbhz"]) -
            vacuum_cn0(float(r["range_m"]))) < 0.02 for r in rows),
        "gas_applied_once": all(float(r["gas_loss_db"]) > 0 and math.isclose(
            float(r["vacuum_cn0_dbhz"]) - float(r["gas_loss_db"]), float(r["postgas_cn0_dbhz"]), abs_tol=1e-9)
            for r in rows),
        "angle_decoded": all(abs(float(r["true_elev_deg"]) - float(r["access_input_deg"])) < 1e-8 for r in rows),
        "matched_polarization": all(r["rx_pol"] == r["tx_pol"] for r in rows),
        "nr_empirical_counts": all(r["oai_curve_sha256"] == curve_sha and physical_rows(r) for r in rows),
        "admission_and_rate_mapping": all(int(r["network_bps"]) == int(t["rate_bps"]) ==
            (int(r["rate_bps"]) if int(r["admitted"]) else 0) for r, t in zip(rows, trace)),
        "propagation_delay": all(math.isclose(float(r["range_m"])/299792458, float(t["delay_s"])) for r,t in zip(rows,trace)),
        "sent": app["sent_packets"] > 0,
        "delivery": app["delivery_ratio"] >= 0.99,
        "goodput": app["payload_mbps"] >= 0.99,
        "latency": app["p95_delay_ms"] is not None and app["p95_delay_ms"] <= 15.0,
    }
    result = {"id":task,"case":case,"passed":all(checks.values()),"checks":checks,"network":app,"oai_sha256":curve_sha,
              "first_sample":{k:rows[0][k] for k in ("gas_loss_db","postgas_cn0_dbhz","prbs","mcs","snr_db","bler","network_bps")}}
    (output/"judgment.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("task",choices=["R01","R02","R03"])
    p.add_argument("--case",choices=["target","regression","holdout"],default="target")
    p.add_argument("--adapter",type=Path)
    p.add_argument("--holdout",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args = p.parse_args()
    if bool(args.holdout) != (args.case == "holdout"):
        p.error("Supply --holdout only for a holdout profile")
    result = run(args.task,args.case,args.adapter or FIXTURES/args.task/"adapter.py",args.output,args.holdout)
    print(json.dumps(result,ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)
