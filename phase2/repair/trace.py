"""Generate a service-link trace with native Skyfield, OpenSatCom, ITU and measured OAI data."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from skyfield.api import EarthSatellite, load, wgs84
from opensatcom.antenna.parametric import ParametricAntenna
from opensatcom.core.models import LinkInputs, PropagationConditions, RFChainModel, Scenario, Terminal
from opensatcom.link.engine import DefaultLinkEngine
from opensatcom.propagation.fspl import FreeSpacePropagation
from phase2.cases.nr import CURVES, select_profile
from phase2.propagation.gas import gas_loss_db
from tasks.repair.trace import load_adapter

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "tasks/repair/scenario.json"
MCS = (4, 12, 20)


def evaluate(task, case, submission, destination, hidden=None):
    config = json.loads(SCENARIO.read_text())
    site = json.loads(hidden.read_text()) if hidden else config["cases"][case]
    adapter = load_adapter(submission)
    times = list(range(0, config["duration_s"], config["cadence_s"]))
    ts = load.timescale(builtin=True)
    satellite = EarthSatellite(*config["tle"], "Hypatia Starlink 0", ts)
    terminal = wgs84.latlon(site["lat_deg"], site["lon_deg"])
    instants = ts.tt_jd([satellite.epoch.tt + (site["start_from_epoch_s"] + t) / 86400 for t in times])
    el, az, dist = (satellite - terminal).at(instants).altaz()
    elevation = el.degrees
    tx_pol = site.get("polarization", "RHCP")
    rx_pol = tx_pol
    if task == "R01":
        old_format = case == "regression"
        values, unit = (el.degrees, "deg") if old_format else (el.radians, "rad")
        elevation = [adapter.elevation_deg(float(value), unit) for value in values]
    elif task == "R02":
        rx_pol = adapter.receiver_polarization(tx_pol if case == "regression" else tx_pol[0])

    bandwidth = site.get("bandwidth_hz", config["bandwidth_hz"])
    carrier = config["carrier_hz"]
    link = LinkInputs(
        Terminal("space", 0, 0, 550000),
        Terminal("ground", site["lat_deg"], site["lon_deg"], 0, system_noise_temp_k=config["noise_temp_k"]),
        Scenario("service-dl", "downlink", carrier, bandwidth, tx_pol,
                 "cn0_dbhz", 0, rx_polarization=rx_pol),
        ParametricAntenna(config["tx_gain_dbi"]), ParametricAntenna(config["rx_gain_dbi"]),
        FreeSpacePropagation(), RFChainModel(tx_power_w=config["tx_power_w"], tx_losses_db=config["tx_losses_db"],
                                            rx_noise_temp_k=config["noise_temp_k"]),
    )
    engine = DefaultLinkEngine()
    env = PropagationConditions()
    nr_digest = hashlib.sha256(CURVES.read_bytes()).hexdigest()
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    with (destination / "trace.csv").open("w") as output:
        trace = csv.writer(output, lineterminator="\n")
        trace.writerow(["time_s", "link_id", "rate_bps", "delay_s"])
        for i, time_s in enumerate(times):
            # Geometry for the physical atmosphere is separated from the faulty receiver admission field.
            true_elev = float(el.degrees[i])
            distance = float(dist.m[i])
            snap = engine.evaluate_snapshot(true_elev, float(az.degrees[i]), distance, link, env)
            gas = gas_loss_db(carrier, true_elev)
            post_cn0 = snap.cn0_dbhz - gas
            phy = select_profile(post_cn0, bandwidth, MCS)
            admitted = elevation[i] >= config["access_min_elev_deg"]
            usable_bps = phy["rate_bps"] if admitted else 0
            exported_bps = usable_bps
            if task == "R03":
                if case == "regression":
                    exported_bps = adapter.service_rate_bps(usable_bps / 1e6, "Mbit/s")
                else:
                    exported_bps = adapter.service_rate_bps(usable_bps / 1e3, "kbit/s")
            propagation_s = distance / 299792458
            trace.writerow([time_s, "service-dl", exported_bps, propagation_s])
            rows.append({
                "time_s": time_s, "range_m": distance, "true_elev_deg": true_elev,
                "access_input_deg": float(elevation[i]), "admitted": int(admitted),
                "tx_pol": tx_pol, "rx_pol": rx_pol, "vacuum_cn0_dbhz": snap.cn0_dbhz,
                "gas_loss_db": gas, "postgas_cn0_dbhz": post_cn0, "allocation_limit_hz": bandwidth,
                **phy, "after_admission_bps": usable_bps, "network_bps": exported_bps,
                "delay_s": propagation_s, "oai_curve_sha256": nr_digest,
            })
    with (destination / "layers.csv").open("w") as output:
        writer = csv.DictWriter(output, rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("id", choices=("R01","R02","R03"))
    parser.add_argument("case", choices=("target","regression","holdout"))
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--holdout", type=Path)
    args = parser.parse_args()
    if bool(args.holdout) != (args.case == "holdout"):
        parser.error("Supply one holdout file only with holdout")
    evaluate(args.id, args.case, args.adapter, args.output, args.holdout)
