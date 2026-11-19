"""Evaluate one deterministic moving service link and export the native ns-3 input."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

from opensatcom.antenna.parametric import ParametricAntenna
from opensatcom.core.models import LinkInputs, OpsPolicy, PropagationConditions, RFChainModel, Scenario, Terminal
from opensatcom.link.engine import DefaultLinkEngine
from opensatcom.modem.acm import HysteresisACMPolicy
from opensatcom.modem.dvbs2 import get_dvbs2_modcod_table, get_dvbs2_performance_curves
from opensatcom.modem.modem import ModemModel
from opensatcom.propagation.fspl import FreeSpacePropagation
from opensatcom.world.network_sim import NetworkWorldSim
from opensatcom.world.providers import PrecomputedTrajectory, StaticEnvironmentProvider
from opensatcom.world.traffic import ConstantTrafficProfile, TrafficDemand
from skyfield.api import EarthSatellite, load, wgs84

ROOT = Path(__file__).resolve().parent


def load_adapter(path):
    spec = importlib.util.spec_from_file_location("submitted_adapter", path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    return adapter


def simulate(task, case, adapter_path, output, holdout=None):
    cfg = json.loads((ROOT / "scenario.json").read_text())
    site = json.loads(Path(holdout).read_text()) if holdout else cfg["cases"][case]
    adapter = load_adapter(adapter_path)
    ts = load.timescale(builtin=True)
    sat = EarthSatellite(*cfg["tle"], "Hypatia Starlink 0", ts)
    station = wgs84.latlon(site["lat_deg"], site["lon_deg"])
    times = list(range(0, cfg["duration_s"], cfg["cadence_s"]))
    instants = ts.tt_jd([sat.epoch.tt + (site["start_from_epoch_s"] + t) / 86400 for t in times])
    alt, az, dist = (sat - station).at(instants).altaz()

    elevation = alt.degrees
    tx_pol = site.get("polarization", "RHCP")
    rx_pol = tx_pol
    if task == "R01":
        unit = "deg" if case == "regression" else "rad"
        values = alt.degrees if unit == "deg" else alt.radians
        elevation = [adapter.elevation_deg(float(value), unit) for value in values]
    elif task == "R02":
        rx_pol = adapter.receiver_polarization(tx_pol if case == "regression" else tx_pol[0])
    traj = PrecomputedTrajectory.from_arrays(times, elevation, az.degrees, dist.m)
    scenario = Scenario("Ku service link", "downlink", cfg["carrier_hz"], site.get("bandwidth_hz", cfg["bandwidth_hz"]),
                        tx_pol, "ebn0_db", cfg["required_ebn0_db"], rx_polarization=rx_pol)
    modes = [m for m in get_dvbs2_modcod_table() if m.name == cfg["modcod"]]
    curves = get_dvbs2_performance_curves()
    acm = HysteresisACMPolicy(modes, curves, cfg["target_bler"])
    modem = ModemModel(modes, curves, cfg["target_bler"], acm)
    link = LinkInputs(
        Terminal("space", 0, 0, 550000),
        Terminal("ground", site["lat_deg"], site["lon_deg"], 0, system_noise_temp_k=cfg["noise_temp_k"]),
        scenario, ParametricAntenna(cfg["tx_gain_dbi"]), ParametricAntenna(cfg["rx_gain_dbi"]),
        FreeSpacePropagation(), RFChainModel(tx_power_w=cfg["tx_power_w"], tx_losses_db=cfg["tx_losses_db"],
                                           rx_noise_temp_k=cfg["noise_temp_k"]), modem,
    )
    env = PropagationConditions()
    # Offer excess demand to export the full available service envelope to the packet scheduler.
    service = NetworkWorldSim().run(
        link, {"sat": traj}, OpsPolicy(min_elevation_deg=cfg["access_min_elev_deg"]),
        StaticEnvironmentProvider(env), ConstantTrafficProfile([TrafficDemand("service", 100.0)]),
    )
    output.mkdir(parents=True, exist_ok=True)
    with (output / "trace.csv").open("w") as raw, (output / "layers.csv").open("w") as diagnostics:
        trace_writer = csv.writer(raw)
        layer_writer = csv.writer(diagnostics)
        trace_writer.writerow(["time_s", "link_id", "rate_bps", "delay_s"])
        layer_writer.writerow(["time_s", "range_m", "true_elev_deg", "access_input_deg", "outage",
                               "rx_pol", "cn0_dbhz", "ebn0_db", "modcod", "bler", "capacity_mbps",
                               "offered_service_bps"])
        for i, time in enumerate(times):
            allocated = float(service.per_user_throughput_mbps["service"][i])
            rate = round(allocated * 1e6)
            if task == "R03":
                if case == "regression":
                    rate = adapter.service_rate_bps(allocated, "Mbit/s")
                else:
                    rate = adapter.service_rate_bps(allocated * 1000, "kbit/s")
            trace_writer.writerow([time, "service-dl", rate, float(dist.m[i]) / 299792458])
            # Diagnostic RF/PHY potential is evaluated even where admission blocks transmission.
            snap = DefaultLinkEngine().evaluate_snapshot(elevation[i], az.degrees[i], dist.m[i], link, env)
            phy = modem.throughput_mbps(snap.ebn0_db, scenario.bandwidth_hz, time)
            layer_writer.writerow([time, dist.m[i], alt.degrees[i], elevation[i],
                                   int(service.base.base.outages_mask[i]), rx_pol, snap.cn0_dbhz,
                                   snap.ebn0_db, phy["selected_modcod"], phy["bler_est"],
                                   allocated, rate])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=["R01", "R02", "R03"])
    parser.add_argument("case", choices=["target", "regression", "holdout"])
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--holdout", type=Path)
    args = parser.parse_args()
    if (args.case == "holdout") != bool(args.holdout):
        parser.error("holdout requires exactly one --holdout scene")
    simulate(args.task, args.case, args.adapter, args.output, args.holdout)
