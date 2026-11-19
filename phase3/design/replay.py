"""Evaluate an allowed stage-three design with the frozen phase-two NR table and ns-3."""
import argparse
import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from phase2.cases.replay import DESIGN, wire, write_evidence
from tasks.regression.network import replay as udp_replay

CURVE = ROOT / "phase2/oai/curves.csv"
TABLE_SHA256 = "3a8cc5db5719600f81c8b1c861461888e639615f851a7e5195b4ac2813d22452"
CASES = {task["id"]:task for task in json.loads((HERE/"specs.json").read_text())}
TLE = [DESIGN["tle"][f] for f in ("name","line1","line2")]


def bind_table():
    if hashlib.sha256(CURVE.read_bytes()).hexdigest() != TABLE_SHA256:
        raise ValueError("Expected the frozen phase-two OAI data")
    os.environ["CHISTAR_NR_CURVES"] = str(CURVE)
    os.environ["CHISTAR_NR_CATALOGUE"] = "extended"


def valid_selection(value, options):
    # Python considers True == 1.0, but JSON booleans are not engineering numbers.
    if type(value) is bool or (isinstance(value,list) and any(type(item) is bool for item in value)):
        return False
    return value in options


def evaluate(spec, candidate, start_s, profile, out):
    choices=spec["choices"]
    if (type(candidate) is not dict or candidate.keys()!=choices.keys()
            or any(not valid_selection(candidate[k],items) for k,items in choices.items())):
        raise ValueError(f"Answer must select one entry per editable field: {choices}")
    config={**spec["fixed"],**candidate}
    site=spec["stations"][config.pop("station",spec["default_station"])]
    epoch_offset=config.pop("start_offset_s",0)
    share=config.pop("dl_slots_per_s",1000)/1000
    offered=spec["offered_mbps"] if profile!="regression" else .15
    minimum=spec["min_payload_mbps"] if profile!="regression" else .14
    duration=spec["duration_s"]
    samples=[dict(time_s=t,orbit_s=start_s+epoch_offset+t,sat_id=0) for t in range(duration)]
    trace=wire(dict(config=config,station=site,tle=TLE,samples=samples))
    for r in trace:
        r["full_downlink_rate_bps"]=r["rate_bps"]
        r["downlink_slots_per_s"]=round(1000*share)
        r["rate_bps"]=round(r["rate_bps"]*share)
    out.mkdir(parents=True,exist_ok=True)
    with (out/"trace.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,["time_s","link_id","rate_bps","delay_s"])
        writer.writeheader()
        for r in trace:
            writer.writerow(dict(time_s=r["time_s"],link_id="downlink",rate_bps=r["rate_bps"],delay_s=r["delay_s"]))
    metrics=udp_replay(out/"trace.csv",offered,duration,out)
    power=config["tx_w"]
    eirp=10*math.log10(power)+config.get("tx_gain_dbi",16.)-config.get("feeder_loss_db",1.5)
    resources=dict(tx_w=power,mean_tx_w=power*share,rx_diameter_m=config.get("rx_diameter_m",.22),
                   bandwidth_hz=config["bandwidth_hz"],eirp_dbw=eirp)
    checks={f"max_{k}":value<=spec["limits"][k]+1e-9 for k,value in resources.items()}
    checks.update(payload=metrics["payload_mbps"]>=minimum,delivery=metrics["delivery_ratio"]>=spec["min_delivery"],
                  latency=metrics["p95_delay_ms"] is not None and metrics["p95_delay_ms"]<=spec["max_p95_ms"],
                  samples=len(trace)==metrics["sample_count"]==duration,
                  radio_to_network=all(r["rate_bps"]==round(share*r["full_downlink_rate_bps"]) for r in trace))
    return write_evidence(out,trace,metrics,checks)


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("id",choices=list(CASES))
    cli.add_argument("--candidate",type=Path,help="JSON with exactly the editable fields; default initial engineering input")
    cli.add_argument("--profile",choices=("main","regression"),default="main")
    cli.add_argument("--output",required=True,type=Path)
    args=cli.parse_args()
    bind_table()
    spec=CASES[args.id]
    candidate=json.loads(args.candidate.read_text()) if args.candidate else spec["initial"]
    epoch=spec["start_s"] if args.profile=="main" else spec["regression_start_s"]
    result=evaluate(spec,candidate,epoch,args.profile,args.output)
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)
