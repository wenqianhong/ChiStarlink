"""Container worker for service-link interface repair tasks."""

import csv
import importlib.util
import json
import math
from functools import lru_cache
from pathlib import Path

from opensatcom.antenna.parametric import ParametricAntenna
from opensatcom.core.models import (
    LinkInputs,
    PropagationConditions,
    RFChainModel,
    Scenario,
    Terminal,
)
from opensatcom.link.engine import DefaultLinkEngine
from opensatcom.propagation.fspl import FreeSpacePropagation
from skyfield.api import EarthSatellite, load, wgs84
from phase2.cases.nr import select_profile
from phase2.propagation.gas import gas_loss_db

WORK = Path("/job")
BASE = json.loads((WORK / "base.json").read_text())
TS = load.timescale(builtin=True)
SAT = EarthSatellite(*BASE["tle"], "Hypatia synthetic Starlink 0", TS)
ENGINE = DefaultLinkEngine()
ENV = PropagationConditions()


@lru_cache(maxsize=None)
def module(path):
    spec = importlib.util.spec_from_file_location("link_interface", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@lru_cache(maxsize=512)
def pass_samples(latitude, longitude, start_s, times):
    station = wgs84.latlon(latitude, longitude)
    instants = TS.tt_jd([SAT.epoch.tt + (start_s + t) / 86400 for t in times])
    alt, az, dist = (SAT - station).at(instants).altaz()
    return list(zip(alt.degrees, az.degrees, dist.m))


def same_value(actual, ideal):
    if isinstance(ideal, (str, list, tuple)):
        return actual == ideal or tuple(actual) == tuple(ideal)
    # The NR rate adapter consumes rounded integer bit/s.
    return math.isclose(actual, ideal, rel_tol=1e-7, abs_tol=1e-7)


def simulate(job):
    spec, scene = job["spec"], job["scene"]
    field = spec["field"]
    adapter = module(WORK / job["decoder"]).decode
    publisher = module(WORK / job["encoder"]).encode
    start = scene["start_from_epoch_s"] + int(spec["id"][1:]) % 7
    times = list(range(job["duration_s"]))
    if "guard" in spec:
        # Retain the exact sub-slot acquisition transition within the 1-s geometry grid.
        times = sorted(set(times + [spec["guard"]]))
    samples = pass_samples(scene["lat_deg"], scene["lon_deg"], start, tuple(times))
    tx_pol = spec.get("polarization", "RHCP")
    if scene.get("relative_pol") == "opposite_label":
        tx_pol = {"H": "V", "V": "H", "LHCP": "RHCP", "RHCP": "LHCP"}[tx_pol]
    reports, traces = [], []
    for t, (true_elev, az, true_range) in zip(times, samples):
        wire_log = {}

        def decode(name, true_value, context=None):
            if name != field:
                return true_value
            message = (
                {"legacy": true_value}
                if job["case"] == "regression"
                else publisher(true_value, context or {})
            )
            actual = adapter(message)
            wire_log.update(
                wire=json.dumps(message, sort_keys=True),
                decoded=json.dumps(actual),
                contract_ok=int(same_value(actual, true_value)),
            )
            return actual

        elev = decode("elevation_deg", float(true_elev))
        mask = decode("mask_deg", spec.get("mask", 10.0))
        distance = decode("range_m", float(true_range))
        carrier = decode("carrier_hz", BASE["carrier_hz"])
        bandwidth = decode("bandwidth_hz", spec.get("bandwidth", BASE["bandwidth_hz"]))
        temp = decode("temp_k", BASE["noise_temp_k"])
        receive_pol = decode("rx_pol", tx_pol)
        link = LinkInputs(
            Terminal("sat", 0, 0, 550000),
            Terminal(
                "ground",
                scene["lat_deg"],
                scene["lon_deg"],
                0,
                system_noise_temp_k=temp,
            ),
            Scenario(
                "Ku service",
                "downlink",
                carrier,
                bandwidth,
                tx_pol,
                "cn0_dbhz",
                0,
                rx_polarization=receive_pol,
            ),
            ParametricAntenna(decode("tx_gain_dbi", BASE["tx_gain_dbi"])),
            ParametricAntenna(decode("rx_gain_dbi", BASE["rx_gain_dbi"])),
            FreeSpacePropagation(),
            RFChainModel(
                tx_power_w=decode("tx_w", scene["tx_w"]),
                tx_losses_db=decode("feed_db", BASE["tx_losses_db"]),
                rx_noise_temp_k=temp,
            ),
        )
        vacuum = ENGINE.evaluate_snapshot(true_elev, az, distance, link, ENV).cn0_dbhz
        gas = decode("gas_db", gas_loss_db(carrier, float(true_elev)))
        cn0 = vacuum - gas
        modes = decode("mcs", [4, 12, 20])
        phy = select_profile(cn0, bandwidth, modes)
        # Retain native precision for byte/bit conversion and probability accounting; round only at export.
        context = {"nominal_bps": phy["tbs_bits"] / phy["slot_s"], "bler": phy["bler"]}
        goodput = context["nominal_bps"] * (1 - phy["bler"])
        transport = decode("coded_rate", goodput, context)
        duty = decode("duty", spec.get("duty", 1.0))
        guard = decode("guard_s", spec.get("guard", 0.0))
        received_usable = elev >= mask and t >= guard
        rate = round(transport * duty) if received_usable else 0
        propagation = decode("delay_s", distance / 299792458)
        fixed = decode("extra_delay_s", spec.get("extra_delay", 0.0))
        total_delay = fixed + propagation
        row = {
            "time_s": t,
            "true_range_m": float(true_range),
            "range_input_m": distance,
            "true_elev_deg": float(true_elev),
            "elev_input_deg": elev,
            "min_elev_deg": mask,
            "admission": int(received_usable),
            "start_guard_s": guard,
            "tx_w": link.rf_chain.tx_power_w,
            "carrier_hz": carrier,
            "bandwidth_hz": bandwidth,
            "rx_pol": receive_pol,
            "tx_pol": tx_pol,
            "rx_temp_k": temp,
            "vacuum_cn0_dbhz": vacuum,
            "gas_db": gas,
            "cn0_dbhz": cn0,
            **phy,
            "duty": duty,
            "network_bps": rate,
            "propagation_s": propagation,
            "processing_s": fixed,
            "delay_s": total_delay,
            **wire_log,
        }
        if not wire_log:
            raise ValueError(f"Unknown interface {field}")
        reports.append(row)
        traces.append(
            dict(time_s=t, link_id="service-dl", rate_bps=rate, delay_s=total_delay)
        )
    out = WORK / "out" / job["key"]
    out.mkdir(parents=True, exist_ok=True)
    for filename, items in (("layers.csv", reports), ("trace.csv", traces)):
        with (out / filename).open("w") as stream:
            writer = csv.DictWriter(stream, items[0].keys(), lineterminator="\n")
            writer.writeheader()
            writer.writerows(items)


if __name__ == "__main__":
    for item in json.loads((WORK / "jobs.json").read_text()):
        simulate(item)
