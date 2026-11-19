"""Container-side OAI point measurements. JSON lines on stdout; no RF hardware."""
import csv
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def measure(job):
    mcs, prbs, snr, trials, seed = [job[k] for k in ("mcs", "prbs", "snr_db", "trials", "seed")]
    cmd = ["/opt/oai/build/nr_dlsim", "-m", "0", "-R", str(job["carrier_prbs"]),
           "-a", "0", "-b", str(prbs), "-e", str(mcs), "-q", "0", "-v", "1",
           "-y", "1", "-z", "1", "-x", "1", "-I", "5", "-H", "1", "-n", str(trials),
           "-s", str(snr), "-S", str(snr + .01), "-t", "0", "-L", "0", "-Z", "native.csv"]
    with tempfile.TemporaryDirectory() as folder:
        result = subprocess.run(cmd, env={**os.environ, "OAI_RNGSEED": str(seed)},
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=folder)
        log = result.stdout.decode(errors="replace")
        if result.returncode:
            raise RuntimeError(f"{cmd} exited {result.returncode}: {log[-5000:]}")
        native_text = (Path(folder) / "native.csv").read_text()
        records = list(csv.DictReader(io.StringIO(native_text)))
    if len(records) != 1:
        raise ValueError(f"Expected one SNR row, found {len(records)} for {job}")
    native = records[0]
    reported_errors, active = map(int, native["n_errors_0"].split("/"))
    count = int(native["false_positive"].split("/")[1])
    if float(native["SNR"]) != snr or count != trials or not 0 <= active <= count or not 0 <= reported_errors <= count:
        raise ValueError(f"Unexpected OAI measurement {job}, {native}")
    if active and not math.isclose(float(native["channel_bler_0"]), reported_errors / active, rel_tol=5.1e-6, abs_tol=5.1e-7):
        raise ValueError(f"Counter and BLER differ: {native}")
    tbs = int(native["TBS"])
    # Single-round eff_rate is earned only when the decoder reports a good TB.
    success = float(native["eff_rate"]) * count / tbs
    if not math.isclose(success, round(success), abs_tol=.0001):
        raise ValueError(f"Non-integer decoded TB count: {native}")
    if not 0 <= round(success) <= active:
        raise ValueError(f"Decoded TB count inconsistent with active trials: {native}")
    return {**job, "active_trials": active, "decoded_tbs": round(success), "tbs_bits": tbs, "reported_errors": reported_errors,
            "errors": count-round(success), "native_csv": native_text, "cmd": cmd,
            "stdout": log, "log_sha256": hashlib.sha256(result.stdout).hexdigest()}


if __name__ == "__main__":
    jobs = json.load(sys.stdin)
    with ThreadPoolExecutor(max_workers=jobs["workers"]) as pool:
        pending = [pool.submit(measure, j) for j in jobs["jobs"]]
        for future in as_completed(pending):
            print(json.dumps(future.result()), flush=True)
