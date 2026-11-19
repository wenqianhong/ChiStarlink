"""Write release evidence from an actual trusted matrix without publishing holdout inputs."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
IDS=("D01","D02","D03","D04","C01","C02","C03")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs_sha256(curve):
    inputs=[ROOT/"tasks/design/tasks.json",ROOT/"tasks/regression/tasks.json",
            ROOT/"phase2/oai/curves.csv",ROOT/"phase2/propagation/gas.py",
            HERE/"nr.py",HERE/"radio.py", HERE/"worker.py",HERE/"replay.py",
            ROOT/"tasks/regression/network.py",ROOT/"tasks/regression/replay.py"]
    return {str(f.relative_to(ROOT)):digest(curve if f.name=="curves.csv" else f) for f in inputs}


def summary(directory):
    provenance=json.loads((directory/"inputs.json").read_text())
    result={**provenance,"tasks":[]}
    for cid in IDS:
        task=json.loads((directory/f"{cid}.json").read_text())
        runs=[]
        for run in task["runs"]:
            if "error" in run:
                runs.append({"stage":run["stage"],"error":run["error"],"expected_pass":run["expected_pass"]})
                continue
            path=directory/"raw"/cid/run["stage"]/"radio.jsonl"
            if digest(path)!=run["radio_sha256"]:
                raise ValueError(f"Evidence changed: {cid} / {run['stage']}")
            traces=[json.loads(line) for line in path.read_text().splitlines()]
            profiles=sorted({(r["prbs"],r["mcs"],r["tbs_bits"]) for r in traces if r["prbs"] is not None})
            keep=["sent_packets","received_packets","payload_mbps","delivery_ratio","p95_delay_ms"]
            entry={k:run[k] for k in ("stage","expected_pass","passed","checks","samples","radio_sha256")}
            entry.update(metrics={k:run["metrics"][k] for k in keep},used_profiles=[
                dict(prbs=p,mcs=m,tbs_bits=t) for p,m,t in profiles])
            runs.append(entry)
        result["tasks"].append({"id":cid,"verified":task["verified"],"runs":runs})
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    p.add_argument("--output",type=Path,default=HERE/"evidence/nr-runs.json")
    args=p.parse_args()
    args.output.write_text(json.dumps(summary(args.directory),indent=2)+"\n")
