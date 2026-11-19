"""Fetch cryptographically pinned upstream archives and build the native NR link simulator."""
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = "chistarlink-oai:dlsim"
SOURCES = {
    "oai": ("OPENAIRINTERFACE/openairinterface5g", "cb98db5b5d2d95c86673821bfc9fa1be9e225b97",
            "7306f5759155914e84c19d09130990484b9345a0199ca49c1cd400bb4b270653"),
    "asn1c": ("mouse07410/asn1c", "940dd5fa9f3917913fd487b13dfddfacd0ded06e",
              "6366c0a0d02eddbdf37f3ecaa2febb2ea08c02a271798181b97d2cb41b07802b"),
    "simde": ("simd-everywhere/simde-no-tests", "1c68d9ad60bf63f3fb527c4ee3b2319d828ffcc6",
              "f6032af6f67496ea0087e54577a2fdac7d1e806fe8ccd19898e21fd5fce3f2e6")
}


def main():
    cache = Path.home() / ".cache/chistarlink/oai"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Path(tmp)
        for name, (repository, commit, checksum) in SOURCES.items():
            source = cache / f"{name}-{commit}.tgz"
            if not source.exists() or hashlib.sha256(source.read_bytes()).hexdigest() != checksum:
                url = f"https://codeload.github.com/{repository}/tar.gz/{commit}"
                subprocess.run(["curl", "-fsSL", "--retry", "3", url, "-o", str(source)], check=True)
            if hashlib.sha256(source.read_bytes()).hexdigest() != checksum:
                raise ValueError(f"Archive checksum mismatch: {repository}")
            shutil.copyfile(source, ctx / f"{name}.tgz")
        cpm = cache / "CPM_0.40.1.cmake"
        cpm_hash = "117cbf2711572f113bab262933eb5187b08cfc06dce0714a1ee94f2183ddc3ec"
        if not cpm.exists() or hashlib.sha256(cpm.read_bytes()).hexdigest() != cpm_hash:
            subprocess.run(["curl", "-fsSL", "--retry", "3",
                            "https://github.com/cpm-cmake/CPM.cmake/releases/download/v0.40.1/CPM.cmake",
                            "-o", str(cpm)], check=True)
        if hashlib.sha256(cpm.read_bytes()).hexdigest() != cpm_hash:
            raise ValueError("CPM checksum mismatch")
        shutil.copyfile(cpm, ctx / "CPM.cmake")
        shutil.copy(HERE / "Dockerfile", ctx)
        subprocess.run(["docker", "build", "-t", IMAGE, str(ctx)], check=True)


if __name__ == "__main__":
    main()
