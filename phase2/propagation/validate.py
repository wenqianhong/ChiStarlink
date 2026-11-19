"""Fetch SHA-256 pinned reference data, then run the ITU-Rpy numerical checks offline."""
import hashlib
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
VECTORS = {
    "slant.csv": (
        "https://raw.githubusercontent.com/inigodelportillo/ITU-Rpy/094abb618c2a7a8cc145e93940f4571650bc2cf5/test/test_data/676/ITURP676-12_A_gas.csv",
        "6a2d649339fedf59f24a96a06b08e1d20348833df0bdb4f4d07ad25b35b79fcd"),
    "official.xlsx": (
        "https://www.itu.int/en/ITU-R/study-groups/rsg3/rwp3m/Validation%20Example/CG-3M3J-13-ValEx-Rev8.3.0.xlsx?download=1",
        "e2d8d864c80f59752318548cdd75d818792b44574da6e41dbdc5cb722aab7546"),
}


def main():
    cache = Path.home() / ".cache/chistarlink/itu"
    cache.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in VECTORS.items():
        path = cache / name
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            subprocess.run(["curl", "--fail", "--retry", "3", "--location", "--output", str(path), url], check=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Digest mismatch for {name}")
    subprocess.run([
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{cache}:/vectors:ro", "-v", f"{HERE}:/work",
        "chistarlink-itur:phase2", "python", "validation.py",
        "--csv", "/vectors/slant.csv", "--xlsx", "/vectors/official.xlsx", "--output", "evidence",
    ], check=True)


if __name__ == "__main__":
    main()
