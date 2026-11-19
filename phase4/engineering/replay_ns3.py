"""Build the upstream MR from a selected revision and run its native scenario and tests."""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = {
    "partial": "9a725b5463a2e953822d5552530a0b2a2d0060fe",
    "fixed": "3336901ecdb1936d61f83ec12c206784ea0afb33",
    "release": "refs/tags/ns-3.42",
}
RUN = """
set -eu
cd /ntn
for suite in three-gpp-ntn-propagation-loss-model circular-aperture-antenna-test geographic-topocentric-test; do
    build/utils/*test-runner --suite=$suite --verbose >> /out/tests.txt
done
cd /out
/ntn/build/src/spectrum/examples/*ntn-channel-example
"""


def summarize(path):
    rows = [list(map(float, line.split())) for line in path.read_text().splitlines()]
    if len(rows) != 100 or any(len(row) != 3 or not all(map(math.isfinite, row))
                               or abs(row[0] - i / 100) > 1e-8 for i, row in enumerate(rows)):
        raise ValueError("Expected 100 finite time/SNR/propagation-gain samples spaced by 0.01 s")
    return {"samples": len(rows), "start_s": rows[0][0], "end_s": rows[-1][0],
            "snr_range_db": [min(row[1] for row in rows), max(row[1] for row in rows)],
            "propagation_gain_range_db": [min(row[2] for row in rows), max(row[2] for row in rows)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", choices=PINS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        parser.error("Use an empty output directory. The upstream example appends to the trace.")
    image = "chistarlink-phase4:ns3-" + args.revision
    pin = PINS[args.revision]
    result = {"upstream": pin}
    with tempfile.TemporaryDirectory() as tmp:
        context = Path(tmp)
        archive = context / "ns3.tgz"
        url = "https://codeload.github.com/nsnam/ns-3-dev-git/tar.gz/" + pin
        urllib.request.urlretrieve(url, archive)
        result["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        shutil.copy(HERE / "ns3-ntn.Dockerfile", context / "Dockerfile")
        with (out / "build.log").open("w") as log:
            build = subprocess.run(["docker", "build", "--progress=plain", "-t", image, str(context)],
                                   stdout=log, stderr=subprocess.STDOUT)
    result["build_exit"] = build.returncode
    if args.revision == "partial":
        reason = "fatal error: ns3/geocentric-constant-position-mobility-model.h: No such file"
        if build.returncode == 0 or reason not in (out / "build.log").read_text():
            raise RuntimeError("Expected upstream cross-module dependency failure was not observed")
    else:
        build.check_returncode()
        subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{out}:/out",
                        image, "bash", "-ec", RUN], check=True)
        result.update(summarize(out / "ntn-snr-trace.txt"))
        result["suite"] = (out / "tests.txt").read_text().splitlines()[0]
        if not result["suite"].startswith("PASS "):
            raise RuntimeError(result["suite"])
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
