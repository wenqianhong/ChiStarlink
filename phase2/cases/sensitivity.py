"""C02 reference/new: replay the same measured radio states at 7 DL slots per 10 ms."""
import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from replay import HERE,c_case,load_fixture
from summarize import digest


def run(output, spec_file):
    cid="C02"
    run_id="main-reference-new"
    base=output/"raw"/cid/run_id
    path=base/"radio.jsonl"
    trusted_record=json.loads((base/"judgment.json").read_text())
    if digest(path)!=trusted_record["radio_sha256"]:
        raise ValueError("Raw trace differs from the verified primary run")
    trace=[json.loads(line) for line in path.read_text().splitlines()]
    spec=importlib.util.spec_from_file_location("private_reference",spec_file)
    trusted=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trusted)
    with tempfile.TemporaryDirectory() as working:
        fixture=load_fixture(Path(working))
        revised=c_case(fixture,cid,trusted.refs[cid],"new",{},output/"sensitivity-700",
                       reused_radio=trace,dl_share=.7)
    return {"id":cid,"stage":run_id,"scheduled_dl_slots_per_second":700,
            "base_trace_sha256":trusted_record["radio_sha256"],
            "base_metrics":trusted_record["metrics"],"sensitivity":revised}


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output",type=Path)
    cli.add_argument("--private",type=Path,default=HERE/"private/specs.py")
    args=cli.parse_args()
    result=run(args.output,args.private)
    (HERE/"evidence/c02-700.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
