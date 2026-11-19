"""Run OAI gNB + UE on RFsim loopback on the pinned descendant build; preserve native logs."""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--timeout",type=int,default=40)
    p.add_argument("--orbital",action="store_true")
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    base=Path("/opt/oai")
    conf=base/"ci-scripts/conf_files"
    gnb_conf=(conf/"gnb.sa.band254.u0.25prb.rfsim.ntn-leo.conf").read_text()
    gnb_conf=gnb_conf.replace("192.168.71.140/26","127.0.0.1/8").replace("192.168.71.132","127.0.0.2")
    (args.out/"gnb-loopback.conf").write_text(gnb_conf)
    gnb=["./nr-softmodem","-O",str(args.out/"gnb-loopback.conf"),"--rfsim"]
    if args.orbital:
        gnb.extend(["--channelmod.use_orbital","1"])
    ue=["./nr-uesoftmodem","-O",str(conf/"nrue.uicc.ntn-leo.conf"),"--rfsim",
        "--rfsimulator.[0].serveraddr","127.0.0.1","--time-sync-I","0.1",
        "--ntn-initial-time-drift","-46","--initial-fo","57340","--cont-fo-comp","3"]
    children=[]
    with (args.out/"gnb.log").open("w") as go,(args.out/"ue.log").open("w") as uo:
        try:
            children.append(subprocess.Popen(gnb,cwd=base/"build",stdout=go,stderr=subprocess.STDOUT))
            time.sleep(2)
            children.append(subprocess.Popen(ue,cwd=base/"build",stdout=uo,stderr=subprocess.STDOUT))
            deadline=time.monotonic()+args.timeout
            while time.monotonic()<deadline and all(proc.poll() is None for proc in children):
                time.sleep(1)
        finally:
            for proc in children:
                if proc.poll() is None:
                    proc.terminate()
            for proc in children:
                try:proc.wait(3)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait()
    (args.out/"run.json").write_text(json.dumps({"gnb":gnb,"ue":ue,"return_codes":[proc.returncode for proc in children],
       "timeout_s":args.timeout,"orbital":args.orbital,"core_attached":False},indent=2)+"\n")


if __name__=="__main__":
    main()
