"""Run the published packet-level workload and return simulator metrics and log files."""
import argparse
import csv
import hashlib
import io
import json
import subprocess
import tarfile
import time
from pathlib import Path
from prepare import RUN, TOPO

IMAGE='chistarlink-hypatia:0ac531c'
BIN='/opt/hypatia/ns3-sat-sim/simulator/build/optimized/scratch/main_satnet/main_satnet'


def read_flows(path):
    with path.open() as f:
        return {int(r[0]):{'src':int(r[1]),'dst':int(r[2]),'rate_mbps':float(r[7]),
                           'packets':int(r[8]),'payload_bytes':int(r[10])} for r in csv.reader(f)}


def execute(input_dir, out, schedule=None, network=None):
    net=network or input_dir/'network'
    out.mkdir(parents=True,exist_ok=True)
    run_path='paper/ns3_experiments/traffic_matrix_load/runs/'+RUN
    bundle=io.BytesIO()
    with tarfile.open(fileobj=bundle,mode='w:gz') as t:
        t.add(input_dir/'run/config_ns3.properties',arcname=run_path+'/config_ns3.properties')
        t.add(schedule or input_dir/'run/udp_burst_schedule.csv',arcname=run_path+'/udp_burst_schedule.csv')
        t.add(net,arcname='paper/satellite_networks_state/gen_data/'+TOPO)
    cmd=f'mkdir /job && cd /job && tar xzf - && {BIN} --run_dir=/job/{run_path} >&2 && cd {run_path}/logs_ns3 && tar czf - *.csv finished.txt'
    start=time.monotonic()
    result=subprocess.run(['docker','run','--rm','--network','none','-i',IMAGE,'sh','-ec',cmd],
                          input=bundle.getvalue(),capture_output=True)
    seconds=time.monotonic()-start
    (out/'console.txt').write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-4000:])
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as t:
        for member in t:
            dest=out/Path(member.name).name
            dest.write_bytes(t.extractfile(member).read())
    if (out/'finished.txt').read_text().strip()!='Yes':
        raise RuntimeError('Incomplete Hypatia run')
    send=read_flows(out/'udp_bursts_outgoing.csv')
    recv=read_flows(out/'udp_bursts_incoming.csv')
    pub=read_flows(input_dir/'published/udp_bursts_incoming.csv')
    assert set(send)==set(recv) and len(send)==100
    sent=sum(f['packets'] for f in send.values());received=sum(f['packets'] for f in recv.values())
    delivery=sorted(recv[f]['packets']/send[f]['packets'] for f in send)
    rates=[f['rate_mbps'] for f in recv.values()]
    info=dict(flows=len(send),sent=sent,received=received,delivery=received/sent,
              aggregate_payload_mbps=sum(rates),bottom_decile_delivery=delivery[9],
              min_delivery=delivery[0],jain_fairness=sum(rates)**2/(len(rates)*sum(x*x for x in rates)),
              published_identical_flows=sum(recv[i]==pub[i] for i in recv),
              observed_vs_published_max_delta_packets=max(abs(recv[i]['packets']-pub[i]['packets']) for i in recv),
              packet_csv_sha256=hashlib.sha256((out/'udp_bursts_incoming.csv').read_bytes()).hexdigest(),
              isl_utilization_sha256=hashlib.sha256((out/'isl_utilization.csv').read_bytes()).hexdigest(),
              wall_seconds=round(seconds,2))
    (out/'summary.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info),flush=True)
    return info

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('input',type=Path);cli.add_argument('output',type=Path)
    cli.add_argument('--schedule',type=Path);cli.add_argument('--network',type=Path)
    a=cli.parse_args();execute(a.input,a.output,a.schedule,a.network)
