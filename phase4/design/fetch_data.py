"""Fetch and verify the reference inputs consumed by the pinned SNS3 scenarios."""
import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from http.client import IncompleteRead
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen

REVISION = "4200675fa10f3eb9ba3627bc664240a331be4ba9"
PREFIXES = (
    "scenarios/geo-33E/", "scenarios/geo-33E-lora/", "scenarios/constellation-leo-2-satellites",
    "scenarios/constellation-eutelsat-geo-2-sats-", "additional-input/utpositions/",
    "additional-input/ext-fadingtraces/input/BeamId-1_", "additional-input/ext-fadingtraces/input/GW",
    "additional-input/antennapatterns/", "additional-input/linkresults/",
    "additional-input/sinrmeaserror/", "additional-input/interferencetraces/",
    "additional-input/rxpowertraces/", "additional-input/fadingtraces/", "sgp4/", "sims/",
)


def fetch(url):
    for retry in range(5):
        request = Request(url, headers={"User-Agent": "ChiStarlink-SNS3-replay"})
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except (OSError, IncompleteRead):
            if retry == 4:
                raise
            sleep(1 + retry)


def git_blob(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def main(target):
    api = f"https://api.github.com/repos/sns3/sns3-data/git/trees/{REVISION}?recursive=1"
    tree = json.loads(fetch(api))
    if tree.get("truncated"):
        raise RuntimeError("Incomplete upstream data inventory")
    files = [row for row in tree["tree"] if row["type"] == "blob" and row["path"].startswith(PREFIXES)]

    def download(row):
        name = row["path"]
        path = target / name
        path.parent.mkdir(exist_ok=True, parents=True)
        symlink = row["mode"] == "120000"
        if path.is_symlink():
            cached = str(path.readlink()).encode()
        elif path.is_file():
            cached = path.read_bytes()
        else:
            cached = None
        if cached is not None and git_blob(cached) == row["sha"] and path.is_symlink() == symlink:
            return
        url = f"https://raw.githubusercontent.com/sns3/sns3-data/{REVISION}/{name}"
        data = fetch(url)
        if git_blob(data) != row["sha"]:
            raise ValueError(f"Git blob verification failed: {name}")
        if path.is_symlink() or path.is_file():
            path.unlink()
        if symlink:
            path.symlink_to(data.decode())
        else:
            path.write_bytes(data)

    with ThreadPoolExecutor(max_workers=10) as workers:
        list(workers.map(download, files))
    print(json.dumps({"data_commit": REVISION, "verified_files": len(files),
                      "bytes": sum(row["size"] for row in files)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    main(parser.parse_args().target)
