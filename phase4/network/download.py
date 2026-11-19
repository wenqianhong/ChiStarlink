"""Download the official snapshot in resumable byte ranges and verify the published digest."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import subprocess
import tempfile
import time

URL = "https://github.com/snkas/hypatia/releases/download/v1/hypatia_paper_temp_data.tar.gz"
SIZE = 500557372
SHA256 = "18d761a28706723b57772e0636fbc40b7d57161f4c54069eede0c8ae740cbe2d"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(dest, workers):
    if dest.exists() and dest.stat().st_size == SIZE and sha256(dest) == SHA256:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    parts = dest.with_name(dest.name + ".parts")
    parts.mkdir(exist_ok=True)
    effective = subprocess.check_output(["curl", "-fsSIL", "-o", "/dev/null", "-w", "%{url_effective}", URL], text=True)
    block = 2**21
    ranges = [(a, min(a+block, SIZE)-1) for a in range(0,SIZE,block)]
    def take(bounds):
        a,b=bounds
        p=parts/str(a)
        for attempt in range(9):
            have=p.stat().st_size if p.exists() else 0
            if have==b-a+1:
                return
            with tempfile.TemporaryDirectory() as tmp:
                data=Path(tmp)/"data"; headers=Path(tmp)/"headers"
                proc=subprocess.run(["curl","-fsSL","--max-time","50","-r",f"{a+have}-{b}",
                                     "-D",str(headers),"-o",str(data),effective],capture_output=True)
                if headers.exists() and f"bytes {a+have}-{b}/{SIZE}" in headers.read_text().lower() and data.is_file():
                    if not 0 < data.stat().st_size <= b-a+1-have:
                        raise ValueError("Invalid range response length")
                    with p.open("ab") as out:
                        out.write(data.read_bytes())
                elif proc.returncode == 0:
                    raise ValueError("Server did not honor byte range")
            if not p.exists() or p.stat().st_size!=b-a+1:
                time.sleep(min(attempt+1,3))
        raise RuntimeError(f"Incomplete byte range {a}..{b}")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(take,ranges))
    with dest.with_suffix(".assembling").open("wb") as out:
        for a,_ in ranges:
            out.write((parts/str(a)).read_bytes())
    assembled=dest.with_suffix(".assembling")
    if sha256(assembled)!=SHA256:
        raise ValueError("Upstream SHA-256 mismatch")
    assembled.replace(dest)
    print("verified",dest,SHA256)

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output",type=Path);cli.add_argument("--workers",type=int,default=8)
    args=cli.parse_args();fetch(args.output,args.workers)
