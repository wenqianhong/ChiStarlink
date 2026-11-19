"""Build the pinned Hypatia/ns-3 image; source archives are verified before use."""
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from network import IMAGE

HERE = Path(__file__).resolve().parent
ARCHIVES = (
    ("hypatia", "0ac531c313eba2335f6344b46347140c3a0d4230", "5e4d91359937aa30f37a024d2eb08037258d293b73f64c615e6340e7a2fc999f"),
    ("basic-sim", "3b32597c183e1039be7f0bede17d36d354696776", "dabb806393a12e77797a13032f87f6036d6b55a9d40898c0c3a117fbc0bb8819")
)


def main():
    cache = Path.home() / ".cache/chistarlink/hypatia"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Path(tmp)
        for name, commit, checksum in ARCHIVES:
            source = cache / f"{name}-{commit}.tgz"
            if not source.exists() or hashlib.sha256(source.read_bytes()).hexdigest() != checksum:
                url = f"https://codeload.github.com/snkas/{name}/tar.gz/{commit}"
                subprocess.run(["curl", "-fsSL", "--retry", "3", url, "-o", str(source)], check=True)
            if hashlib.sha256(source.read_bytes()).hexdigest() != checksum:
                raise RuntimeError(f"Archive checksum mismatch: {name}")
            shutil.copyfile(source, ctx / f"{name}.tgz")
        for filename in ("service-link.cc", "Dockerfile"):
            shutil.copyfile(HERE / filename, ctx / filename)
        subprocess.run(["docker", "build", "-t", IMAGE, str(ctx)], check=True)


if __name__ == "__main__":
    main()
