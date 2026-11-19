"""Export a spec and pinned simulator core without upstream Case 3 implementations or logs."""
import argparse
import io
import subprocess
import zipfile
from pathlib import Path

REVISION = "aa738929bc5fa6c41217f96b8a1c6fac35ee802b"
HERE = Path(__file__).resolve().parent


def export(source, output):
    args = ["git", "-C", str(source)]
    core = subprocess.check_output(args + ["archive", "--format=zip", REVISION, "src", "resource",
                                         "configuration", "requirements.txt", "LICENSE", "CITATION.cff"])
    fixtures = {"simulation_config.py": "src/configuration/simulation_config.py",
                "user_groups.py": "experiment/data/user_groups.py"}
    with zipfile.ZipFile(io.BytesIO(core)) as original, zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as target:
        for info in original.infolist():
            target.writestr(info, original.read(info.filename))
        for name, path in fixtures.items():
            content = subprocess.check_output(args + ["show", f"{REVISION}:cases/case3/{path}"])
            target.writestr(f"inputs/{name}", content)
        target.write(HERE / "SPEC.md", "SPEC.md")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("source", type=Path)
    cli.add_argument("output", type=Path)
    options = cli.parse_args()
    export(options.source, options.output)
