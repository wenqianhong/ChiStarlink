"""Prepare a verified SNS3 Docker build context and build its native simulations."""
import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

import fetch_data

HERE = Path(__file__).resolve().parent
SOURCES = {
    "ns-3.48.tar.bz2": (
        "https://www.nsnam.org/releases/ns-3.48.tar.bz2",
        "5700ceecef2c9bc862502914b2237fe798d4c7ae07652247050e300e49407c4d",
    ),
    "satellite.tgz": ("sns3/sns3-satellite/2c0c6d4d7fd1628eda1b923a7e135749513769fa",
                      "67da1729adafa945ddea8731002a87abf498c6d630b6d1ab76478c0b3009acc5"),
    "traffic.tgz": ("sns3/traffic/2710ed71c2cba9d92940bdf53ad85159504329d9",
                    "f1307229030eb5b713b32cddbb5cc6de9aabe566cff6109922ca973016885219"),
    "magister-stats.tgz": ("sns3/stats/003f6a29ce74808d0b2579fd16a9718f793f5bfe",
                           "f4de23332a1e12289fb04cd3c75d983cb8c1f166cfd53619eae9f3335fdf7b62"),
}


def build(context):
    context.mkdir(exist_ok=True, parents=True)
    for name, (source, digest) in SOURCES.items():
        archive = context / name
        if archive.exists() and hashlib.sha256(archive.read_bytes()).hexdigest() == digest:
            continue
        if not source.startswith("https://"):
            repo, commit = source.rsplit("/", 1)
            source = f"https://codeload.github.com/{repo}/tar.gz/{commit}"
        subprocess.run(["curl", "-fLsS", "--retry", "5", "--retry-all-errors",
                        source, "-o", str(archive)], check=True)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Archive hash mismatch: {name}")
    fetch_data.main(context / "data")
    for name in ("Dockerfile", "native-build.sh"):
        shutil.copyfile(HERE / name, context / name)
    subprocess.run(["docker", "build", "-t", "chistarlink-sns3:3.48", str(context)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context", type=Path, help="dedicated build cache directory")
    build(parser.parse_args().context)
