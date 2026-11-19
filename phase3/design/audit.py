"""Independent PyEphem geometry and ns-3 counter/resource audit of the trusted design matrix."""
import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import ephem
from replay import CASES,HERE,TLE
from release import LABELS


def tle_epoch(line1):
    value=line1[18:32]
    year=int(value[:2])
    return datetime(1900+year if year>=57 else 2000+year,1,1)+timedelta(days=float(value[2:])-1.)


def audit(raw, trusted):
    start=tle_epoch(TLE[1])
    satellite=ephem.readtle(*TLE)
    records=0
    samples=0
    horizon=0
    max_range=0.
    max_el=0.
    max_az=0.
    max_los=0.
    az_peak_elevation=0.
    nearest_mask=math.inf
    for cid,s in CASES.items():
        key=trusted[cid]
        assert abs(key["holdout_start_s"]-s["start_s"])>3600
        assert s["regression_start_s"]>=s["start_s"]+s["duration_s"]
        for name in LABELS:
            result=json.loads((raw/cid/name/"judgment.json").read_text())
            times=[json.loads(line) for line in (raw/cid/name/"radio.jsonl").read_text().splitlines()]
            initial=name.endswith("_initial")
            control=s["initial"] if initial else key["reference"]
            assert control.keys()==s["choices"].keys()
            assert all(type(v) is not bool and v in s["choices"][k] for k,v in control.items())
            cfg={**s["fixed"],**control}
            assert 1e9<=cfg["frequency_hz"]<=350e9 and 5<=cfg["min_elev_deg"]<=90
            bw=cfg["bandwidth_hz"]
            assert 0<bw<=s["limits"]["bandwidth_hz"] and cfg.get("noise_k",290)>0
            diameter=cfg.get("rx_diameter_m",.22)
            watts=cfg["tx_w"]
            duty=cfg.get("dl_slots_per_s",1000)/1000
            eirp=10*math.log10(watts)+cfg.get("tx_gain_dbi",16)-cfg.get("feeder_loss_db",1.5)
            assert 0<diameter<=s["limits"]["rx_diameter_m"] and 0<watts<=s["limits"]["tx_w"]
            assert 0<duty<=1 and watts*duty<=s["limits"]["mean_tx_w"]+1e-9
            assert eirp<=s["limits"]["eirp_dbw"]+1e-9
            site=s["stations"][control.get("station",s["default_station"])]
            observer=ephem.Observer()
            observer.lat,observer.lon=map(str,site[:2])
            observer.elevation=site[2]
            observer.pressure=0
            start_s=s["start_s"]
            if name.startswith("holdout"): start_s=key["holdout_start_s"]
            if name.startswith("regression"): start_s=s["regression_start_s"]
            start_s+=control.get("start_offset_s",0)
            for sec,r in enumerate(times):
                assert r["time_s"]==sec and r["orbit_s"]==start_s+sec and r["sat_id"]==0
                observer.date=start+timedelta(seconds=start_s+sec)
                satellite.compute(observer)
                alt=math.degrees(float(satellite.alt))
                az=math.degrees(float(satellite.az))
                max_range=max(max_range,abs(float(satellite.range)-r["range_m"]))
                max_el=max(max_el,abs(alt-r["elevation_deg"]))
                az_error=abs((az-r["azimuth_deg"]+180)%360-180)
                if az_error>max_az:
                    max_az,az_peak_elevation=az_error,alt
                # Compare the true directional separation, since azimuth is singular at zenith.
                delta_el=math.radians(alt-r["elevation_deg"])
                hav=math.sin(delta_el/2)**2 + math.cos(math.radians(alt))*math.cos(math.radians(r["elevation_deg"]))*math.sin(math.radians(az_error)/2)**2
                max_los=max(max_los,math.degrees(2*math.asin(math.sqrt(min(1.,hav)))))
                nearest_mask=min(nearest_mask,abs(alt-cfg["min_elev_deg"]))
                admitted=alt>=cfg["min_elev_deg"]
                assert admitted==(r["prbs"] is not None)
                if admitted: assert r["prbs"]*12*r["scs_hz"]<=bw
                else:
                    assert r["rate_bps"]==0
                    horizon+=1
            count=json.loads((raw/cid/name/"metrics.json").read_text())
            assert count==result["metrics"]
            sent,recv=count["sent_packets"],count["received_packets"]
            duration=s["duration_s"]
            offered=.15 if name.startswith("regression") else s["offered_mbps"]
            limit=.14 if name.startswith("regression") else s["min_payload_mbps"]
            assert 0<=recv<=sent and abs(sent-offered*1e6*duration/8000)<=1.01
            assert len(times)==count["sample_count"]==duration
            goodput=recv*8000/(duration*1e6)
            delivery=recv/sent
            assert abs(goodput-count["payload_mbps"])<1e-9
            assert abs(delivery-count["delivery_ratio"])<1e-10
            assert (count["p95_delay_ms"] is None)==(recv==0)
            delay=count["p95_delay_ms"]
            passed=goodput>=limit and delivery>=s["min_delivery"] and delay is not None and 0<=delay<=s["max_p95_ms"]
            assert passed==result["passed"]==(not initial)
            samples+=len(times)
            records+=1
    # Independent implementation, same UTC and no refraction. Azimuth is more sensitive near zenith.
    assert max_range<500 and max_el<.1 and max_los<.1
    return dict(stage_count=records,samples=samples,zero_access_samples=horizon,
                max_range_difference_m=max_range,max_elevation_difference_deg=max_el,
                max_azimuth_difference_deg=max_az,elevation_at_max_az_difference_deg=az_peak_elevation,
                max_3d_direction_difference_deg=max_los,min_elevation_mask_distance_deg=nearest_mask,
                geometry="PyEphem 4.2.1, atmospheric refraction disabled",
                resources_and_udp_rechecked=True,passed=True)


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--raw",type=Path,default=HERE/"private/runs")
    cli.add_argument("--trusted",type=Path,default=HERE/"private/trusted.json")
    args=cli.parse_args()
    print(json.dumps(audit(args.raw,json.loads(args.trusted.read_text())),indent=2))
