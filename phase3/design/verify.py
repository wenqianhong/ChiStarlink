"""Trusted validation over five actual container replays per design."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from replay import CASES, HERE, bind_table, evaluate


def verify(spec, private_inputs, work):
    cid=spec["id"]
    ref=private_inputs[cid]["reference"]
    hold=private_inputs[cid]["holdout_start_s"]
    runs={}
    for label,candidate,epoch,profile in [
        ("main_initial",spec["initial"],spec["start_s"],"main"),
        ("main_reference",ref,spec["start_s"],"main"),
        ("holdout_initial",spec["initial"],hold,"holdout"),
        ("holdout_reference",ref,hold,"holdout"),
        ("regression_reference",ref,spec["regression_start_s"],"regression")]:
        try:
            result=evaluate(spec,candidate,epoch,profile,work/cid/label)
            result["expected_pass"]=label.endswith("_reference")
            runs[label]=result
        except Exception as exc:
            runs[label]={"error":str(exc)}
    verified=all(r.get("passed") is not None and r["passed"]==r["expected_pass"] for r in runs.values())
    for name in ("main","holdout"):
        left,right=runs[f"{name}_initial"],runs[f"{name}_reference"]
        verified=verified and left["radio_sha256"]!=right["radio_sha256"]
    summary={"id":cid,"verified":verified,"runs":runs}
    (work/cid).mkdir(parents=True,exist_ok=True)
    (work/cid/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(cid,"PASS" if verified else "FILTER",[(k,round(v.get("metrics",{}).get("payload_mbps",0),3),v.get("passed")) for k,v in runs.items()],flush=True)
    return summary


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--private",type=Path,default=HERE/"private/trusted.json")
    cli.add_argument("--output",type=Path,default=HERE/"private/runs")
    cli.add_argument("--id",action="append",choices=list(CASES))
    cli.add_argument("--workers",type=int,default=3)
    args=cli.parse_args()
    bind_table()
    private=json.loads(args.private.read_text())
    ids=args.id or list(CASES)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results=list(pool.map(lambda key:verify(CASES[key],private,args.output), ids))
    print(f"Confirmed {sum(r['verified'] for r in results)} / {len(results)}")
    raise SystemExit(0 if all(r["verified"] for r in results) else 1)
