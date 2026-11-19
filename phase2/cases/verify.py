"""Trusted evaluator. Rerun the seven NR cases and record unexpected outcomes too."""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from replay import CHANGES, DESIGN, HERE, ROOT, RADIO_IMAGE, c_case, d_case, initial, load_fixture
from summarize import digest, inputs_sha256


def run_one(cid, trusted, fixture, output):
    reference=trusted.refs[cid]
    if cid in CHANGES:
        stages=[]
        for window,params in [("main",{}),("holdout",trusted.secondary(cid))]:
            for label,settings in [("initial",{}),("reference",reference)]:
                for goal in ("old","new"):
                    stages.append((f"{window}-{label}-{goal}",
                                   not (label=="initial" and goal=="new"),
                                   (fixture,cid,settings,goal,params)))
        run=c_case
    else:
        stages=[("initial",False,(cid,initial(cid),"target",0)),
                ("reference",True,(cid,reference,"target",0)),
                ("regression",True,(cid,reference,"regression",0)),
                ("holdout",True,(cid,reference,"target",trusted.secondary(cid)["start_offset_s"]))]
        run=d_case
    records=[]
    for label,expected,args in stages:
        record={"stage":label,"expected_pass":expected}
        try:
            result=run(*args,output/"raw"/cid/label)
            record.update(result)
            print(cid,label,round(result["metrics"]["payload_mbps"],3),result["passed"],flush=True)
        except Exception as error:
            record["error"]=str(error)
            print(cid,label,"runtime error",str(error)[-350:],flush=True)
        records.append(record)
    summary={"id":cid,"verified":all(r.get("passed") is r["expected_pass"] for r in records),
             "runs":records}
    (output/f"{cid}.json").write_text(json.dumps(summary,indent=2)+"\n")
    return summary


if __name__ == "__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--task",action="append",choices=[*DESIGN["cases"],*CHANGES])
    cli.add_argument("--curves",type=Path,default=ROOT/"phase2/oai/curves.csv")
    cli.add_argument("--catalogue",choices=["first-four","extended"],default="extended")
    cli.add_argument("--private",type=Path,default=HERE/"private/specs.py")
    cli.add_argument("--output",type=Path,default=HERE/"private/first-attempt")
    args=cli.parse_args()
    args.output.mkdir(exist_ok=True,parents=True)
    frozen=args.output.resolve()/f"curves-{digest(args.curves)}.csv"
    if not frozen.exists():
        shutil.copyfile(args.curves,frozen)
        frozen.chmod(0o444)
    if digest(frozen)!=digest(args.curves):
        raise ValueError("Wrong frozen curve snapshot")
    os.environ["CHISTAR_NR_CURVES"]=str(frozen)
    os.environ["CHISTAR_NR_CATALOGUE"]=args.catalogue
    provenance={"inputs_sha256":inputs_sha256(frozen),"catalogue":args.catalogue,
                "images":{tag:subprocess.check_output(["docker","image","inspect","--format","{{.Id}}",tag],text=True).strip()
                          for tag in (RADIO_IMAGE,"chistarlink-hypatia:0ac531c")}}
    (args.output/"inputs.json").write_text(json.dumps(provenance,indent=2)+"\n")
    loader=importlib.util.spec_from_file_location("candidate_specs",args.private)
    trusted=importlib.util.module_from_spec(loader)
    loader.loader.exec_module(trusted)
    ids=args.task or [*DESIGN["cases"],*CHANGES]
    with tempfile.TemporaryDirectory() as working:
        fixture=load_fixture(Path(working)) if any(cid in CHANGES for cid in ids) else None
        with ThreadPoolExecutor(max_workers=3) as threads:
            result=list(threads.map(lambda c:run_one(c,trusted,fixture,args.output),ids))
    if inputs_sha256(frozen)!=provenance["inputs_sha256"]:
        raise RuntimeError("Radio, network or task input changed during matrix; rerun required")
    print("Verified",sum(r["verified"] for r in result),"of",len(result))
    raise SystemExit(0 if all(r["verified"] for r in result) else 1)
