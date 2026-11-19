"""Containerized NR case replay. Preserve first-stage specifications and inputs."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT))
from tasks.regression import replay as hypatia
from tasks.regression.network import replay as replay_udp

DESIGN = json.loads((ROOT/"tasks/design/tasks.json").read_text())
CHANGES = {s["id"]:s for s in json.loads((ROOT/"tasks/regression/tasks.json").read_text())}
RADIO_IMAGE = "chistarlink-itur:phase2"
DEFAULT_MCS = [4,8,12,14,16,18,20,26]
CATALOGUES = {"first-four":[4,12,20,26], "extended":DEFAULT_MCS}


def wire(job):
    bundle = io.BytesIO()
    files = [HERE/"worker.py", HERE/"radio.py", HERE/"nr.py", ROOT/"phase2/propagation/gas.py"]
    curves = None
    if not job.get("aperture_check"):
        curves = Path(os.environ.get("CHISTAR_NR_CURVES", ROOT/"phase2/oai/curves.csv"))
        catalogue = CATALOGUES[os.environ.get("CHISTAR_NR_CATALOGUE","extended")]
        selected = job["config"].get("mcs", catalogue)
        job["config"] = {**job["config"], "mcs":[m for m in selected if m in catalogue]}
        if not job["config"]["mcs"]:
            raise ValueError("Empty modem catalogue")
    with tarfile.open(fileobj=bundle,mode="w:gz") as tar:
        for path in files:
            tar.add(path, arcname=str(path.relative_to(ROOT)))
        if curves:
            tar.add(curves, arcname="phase2/oai/curves.csv")
        body = json.dumps(job).encode()
        entry = tarfile.TarInfo("input.json")
        entry.size = len(body)
        tar.addfile(entry,io.BytesIO(body))
    cmd = ["docker","run","--rm","--network","none","-i",RADIO_IMAGE,"sh","-ec",
           "cd /tmp && tar xzf - && python -m phase2.cases.worker < input.json"]
    proc = subprocess.run(cmd,input=bundle.getvalue(),capture_output=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors="replace"))
    return json.loads(proc.stdout)


def write_evidence(out, trace, metrics, checks):
    out.mkdir(parents=True, exist_ok=True)
    raw = "".join(json.dumps(t,sort_keys=True,allow_nan=False)+"\n" for t in trace).encode()
    (out/"radio.jsonl").write_bytes(raw)
    result = {"passed":all(checks.values()),"checks":checks,"metrics":metrics,
              "samples":len(trace),"radio_sha256":hashlib.sha256(raw).hexdigest()}
    (out/"judgment.json").write_text(json.dumps(result,indent=2)+"\n")
    return result


def initial(case_id):
    if case_id in CHANGES:
        return CHANGES[case_id]["initial"].copy()
    config = DESIGN["cases"][case_id]["initial"].copy()
    if "modes" in config:
        config.pop("modes")
        config["mcs"] = [4]
    return config


def d_case(cid, settings, profile, offset, out):
    spec = DESIGN["cases"][cid]
    candidate = settings.copy()
    if set(candidate) != set(initial(cid)):
        raise ValueError(f"Expected editable fields {list(initial(cid))}")
    for key,value in candidate.items():
        if key == "mcs":
            if not value or not set(value).issubset(DEFAULT_MCS):
                raise ValueError("MCS not available in NR catalogue")
        elif value not in spec["choices"][key]:
            raise ValueError(f"Value outside catalogue: {key}={value}")
    site = candidate.pop("station",spec["station"])
    spec_radio = {**spec["radio"],**candidate}
    duration = spec["duration_s"]
    start = spec["start_s"] + (-30 if profile=="regression" else offset)
    fraction = .15 if profile=="regression" else spec["offered_mbps"]
    t = DESIGN["tle"]
    trace = wire({"config":spec_radio,"station":[*DESIGN["stations"][site],0.],
                  "tle":[t["name"],t["line1"],t["line2"]],
                  "samples":[dict(time_s=i,orbit_s=start+i,sat_id=0) for i in range(duration)]})
    out.mkdir(parents=True,exist_ok=True)
    with (out/"trace.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,["time_s","link_id","rate_bps","delay_s"])
        w.writeheader()
        for r in trace:
            w.writerow(dict(time_s=r["time_s"],link_id="ground-downlink",rate_bps=r["rate_bps"],delay_s=r["delay_s"]))
    metrics = replay_udp(out/"trace.csv",fraction,duration,out)
    checks = {"sample_count":len(trace)==duration==metrics["sample_count"],
              "propagation_delay":all(math.isclose(r["range_m"]/299792458.,r["delay_s"]) for r in trace),
              "payload":metrics["payload_mbps"] >= (.14 if profile=="regression" else spec["min_payload_mbps"]),
              "delivery":metrics["delivery_ratio"]>=spec["min_delivery"],
              "delay":metrics["p95_delay_ms"] is not None and metrics["p95_delay_ms"]<=spec["max_p95_ms"]}
    return write_evidence(out,trace,metrics,checks)


def load_fixture(working):
    fixture = working/"fixture"
    hypatia.get_fixture(fixture)
    network = fixture/"satellite_network_state"
    with tarfile.open(network/f"{hypatia.ROUTES}.tar.gz") as archive:
        archive.extractall(network)
    return fixture


def configure_link(network, config, end_ns, reused_radio=None, dl_share=1.):
    if not math.isfinite(dl_share) or not 0 <= dl_share <= 1:
        raise ValueError("Scheduled downlink fraction must lie in [0, 1]")
    dynamic=network/hypatia.ROUTES
    station=[float(x) for x in hypatia.rows(network/"ground_stations.txt")[1][2:5]]
    tle=(network/"tles.txt").read_text().splitlines()[1:]
    source=len(tle)//3
    dest=source+1
    next_hop={}
    samples=[]
    for time in range(0,end_ns,hypatia.INTERVAL_NS):
        for node, destination, hop, txif, rxif in hypatia.rows(dynamic/f"fstate_{time}.txt"):
            if int(destination)==dest:
                next_hop[int(node)]=(int(hop),int(txif),int(rxif))
        route=[source]
        while route[-1]!=dest:
            hop=next_hop[route[-1]][0]
            if hop<0 or hop in route:
                raise ValueError("Missing or looping upstream routing state")
            route.append(hop)
        sid=route[-2]
        samples.append(dict(time_s=time/1e9,orbit_s=time/1e9,sat_id=sid,route=route,
                            target=dest,hop=next_hop[sid]))
    if reused_radio is None:
        trace=wire(dict(config=config,station=station,tle=tle,samples=samples))
    else:
        trace=[row.copy() for row in reused_radio]
        if len(samples)!=len(trace):
            raise ValueError("Reuse trace length differs from actual route sampling")
        for base, row in zip(samples,trace):
            if base["time_s"]!=row["time_s"] or base["route"]!=row["route"] or tuple(base["hop"])!=tuple(row["hop"]):
                raise ValueError("Reuse trace does not fit native topology")
    if reused_radio is not None or dl_share != 1.:
        for row in trace:
            row["full_downlink_rate_bps"]=row["rate_bps"]
            row["scheduled_dl_fraction"]=dl_share
            row["rate_bps"]=round(row["rate_bps"]*dl_share)
    previously_down=set()
    for r in trace:
        time=round(r["time_s"]*1e9)
        sid=r["sat_id"]
        rate=r["rate_bps"]
        if not rate or sid in previously_down:
            pair = r["hop"] if rate else [-1,-1,-1]
            with (dynamic/f"fstate_{time}.txt").open("a") as f:
                print(sid,dest,*pair,sep=",",file=f)
            if rate==0:
                previously_down.add(sid)
                continue
            previously_down.discard(sid)
        physical_fraction=min(1.,rate/(hypatia.GSL_MBPS*1e6))
        with (dynamic/f"gsl_if_bandwidth_{time}.txt").open("a") as f:
            print(f'{sid},{r["hop"][1]},{physical_fraction:.10f}',file=f)
    return trace


def c_case(fixture,cid,proposal,requirement,holdout,out,reused_radio=None,dl_share=1.):
    spec=CHANGES[cid]
    limits=spec[requirement]
    if set(proposal)-set(spec["editable"]):
        raise ValueError("Changing fields outside editable scope")
    if not all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in proposal.values()):
        raise ValueError("Invalid engineering parameter")
    config={**spec["initial"],**proposal}
    if "rx_diameter_m" in limits:
        config["rx_diameter_m"]=limits["rx_diameter_m"]
    if holdout:
        config["noise_k"]=holdout["noise_k"]
    start=holdout.get("start_s",0)
    duration=holdout.get("duration_s",8)
    end=round((start+duration+.5)*1e9)
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)/"case"
        shutil.copytree(fixture,root,ignore=shutil.ignore_patterns(hypatia.ROUTES,"logs_ns3"))
        net=root/"satellite_network_state"
        dynamic=net/hypatia.ROUTES
        dynamic.mkdir()
        for time in range(0,end,hypatia.INTERVAL_NS):
            for prefix in ["fstate","gsl_if_bandwidth"]:
                name=f"{prefix}_{time}.txt"
                shutil.copyfile(fixture/"satellite_network_state"/hypatia.ROUTES/name,dynamic/name)
        prop=root/"run/config_ns3.properties"
        prop.write_text(prop.read_text().replace("200000000000\n",f"{end}\n"))
        (root/"run/udp_burst_schedule.csv").write_text(
            f'0,17,18,{limits["offered_mbps"]},{round(start*1e9)},{round(duration*1e9)},,\n')
        trace=configure_link(net,config,end,reused_radio,dl_share)
        metrics=hypatia.execute(root)
        for name in ["udp_bursts_outgoing.csv","udp_bursts_incoming.csv",
                     "udp_burst_0_incoming.csv","udp_burst_0_outgoing.csv","finished.txt"]:
            f=root/"run/logs_ns3"/name
            if f.exists(): shutil.copy(f,out/name)
    checks=dict(payload=metrics["payload_mbps"]>=limits["min_payload_mbps"],delivery=metrics["delivery_ratio"]>=.98,
                delay=metrics["p95_delay_ms"] is not None and metrics["p95_delay_ms"]<=100.,
                power=config["tx_w"]<=limits["max_tx_w"],aperture=config.get("rx_diameter_m",.22)<=.35)
    return write_evidence(out,trace,metrics,checks)


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("case",choices=[*DESIGN["cases"],*CHANGES])
    cli.add_argument("--candidate",type=Path)
    cli.add_argument("--profile",choices=["target","regression","old","new"])
    cli.add_argument("--output",type=Path,required=True)
    args=cli.parse_args()
    candidate=json.loads(args.candidate.read_text()) if args.candidate else None
    if args.case in CHANGES:
        if args.profile not in (None,"old","new"): cli.error("C cases require old/new")
        with tempfile.TemporaryDirectory() as working:
            result=c_case(load_fixture(Path(working)),args.case,candidate or {},args.profile or "new",{},args.output)
    else:
        if args.profile not in (None,"target","regression"): cli.error("D cases require target/regression")
        result=d_case(args.case,candidate or initial(args.case),args.profile or "target",0,args.output)
    print(json.dumps(result))
    sys.exit(0 if result["passed"] else 1)
