"""Audit raw receiver evidence and release records against independent OAI error counts."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(matrix, summary_path, curves):
    result=json.loads(summary_path.read_text())
    for rel, expected in result["inputs_sha256"].items():
        actual=curves if rel=="phase2/oai/curves.csv" else ROOT/rel
        assert digest(actual)==expected,(rel,"input hash mismatch")
    with curves.open() as f:
        table={(int(row["prbs"]),int(row["mcs"]),float(row["snr_db"])):row for row in csv.DictReader(f)}
    effective=0
    total=0
    runs=0
    for case in result["tasks"]:
        for stage in case["runs"]:
            folder=matrix/"raw"/case["id"]/stage["stage"]
            evidence=folder/"radio.jsonl"
            assert digest(evidence)==stage["radio_sha256"]
            judging=json.loads((folder/"judgment.json").read_text())
            assert stage["passed"]==judging["passed"]
            for line in evidence.open():
                r=json.loads(line)
                total+=1
                if r["prbs"] is None:
                    assert r["rate_bps"]==0
                    continue
                effective+=1
                key=(r["prbs"],r["mcs"])
                lo=table[(*key,r["lower_snr_db"])]
                hi=table[(*key,r["upper_snr_db"])]
                assert int(lo["tbs_bits"])==int(hi["tbs_bits"])==r["tbs_bits"]
                assert r["lower_errors"]==int(lo["errors"]) and r["upper_errors"]==int(hi["errors"])
                assert r["lower_trials"]==int(lo["trials"]) and r["upper_trials"]==int(hi["trials"])
                assert r["lower_snr_db"]<=r["snr_db"]<=r["upper_snr_db"]
                freq_hz=int(lo["prbs"])*12*int(lo["scs_hz"])
                assert abs((r["cn0_dbhz"]-10*math.log10(freq_hz))-r["snr_db"])<1e-9
                assert abs((r["cn0_free_space_dbhz"]-r["gas_db"])-r["cn0_dbhz"])<1e-9
                x0,x1=r["lower_snr_db"],r["upper_snr_db"]
                mix=0 if x0==x1 else (r["snr_db"]-x0)/(x1-x0)
                bler=(1-mix)*int(lo["errors"])/int(lo["trials"])+mix*int(hi["errors"])/int(hi["trials"])
                assert abs(bler-r["bler"])<1e-12
                assert abs((1-bler)*int(lo["tbs_bits"])/float(lo["slot_s"])-r["rate_bps"])<=.500001
            runs+=1
    return {"passed":True,"nr_table_sha256":digest(curves),"stages_checked":runs,
            "radio_samples":total,"in_view_sample_checks":effective}


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("matrix",type=Path)
    cli.add_argument("--summary",type=Path,default=HERE/"evidence/nr-runs.json")
    cli.add_argument("--curves",type=Path,default=ROOT/"phase2/oai/curves.csv")
    args=cli.parse_args()
    print(json.dumps(audit(args.matrix,args.summary,args.curves),indent=2))
