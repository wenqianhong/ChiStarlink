"""Directional Ku-band service link. Use OpenSatCom v0.7.0 and SI units."""
import math
from functools import lru_cache

from opensatcom.antenna.parametric import ParametricAntenna
from opensatcom.core.models import LinkInputs, PropagationConditions, RFChainModel, Scenario, Terminal
from opensatcom.link.engine import DefaultLinkEngine
from opensatcom.modem.acm import HysteresisACMPolicy
from opensatcom.modem.dvbs2 import get_dvbs2_modcod_table, get_dvbs2_performance_curves
from opensatcom.modem.modem import ModemModel
from opensatcom.propagation.fspl import FreeSpacePropagation

LIGHT_SPEED = 299792458.0
DEFAULTS = dict(frequency_hz=12e9, bandwidth_hz=1e6, tx_w=2.0,
                feeder_loss_db=1.5, tx_gain_dbi=16.0, rx_diameter_m=0.22,
                efficiency=0.6, noise_k=290., pointing_deg=0.2, min_elev_deg=10.,
                modes=["QPSK_1/2", "8PSK_3/4"])
ENGINE = DefaultLinkEngine()


@lru_cache(maxsize=32)
def fixed_modem(name):
    """One native ModemModel per fixed candidate; no ACM state across candidates."""
    mode = next(m for m in get_dvbs2_modcod_table() if m.name == name)
    curves = get_dvbs2_performance_curves()
    policy = HysteresisACMPolicy([mode], curves, 0.01)
    modem = ModemModel([mode], curves, 0.01, policy)
    return mode, modem


def evaluate(config, elevation_deg, azimuth_deg, range_m, time_s):
    """Return radio trace for a single epoch. Config may override DEFAULTS."""
    c = {**DEFAULTS, **config}
    delay = range_m / LIGHT_SPEED
    result = dict(delay_s=delay, modcod="outage", rate_bps=0, cn0_dbhz=None,
                  bler=None, ebn0_db=None)
    if elevation_deg < c["min_elev_deg"]:
        return result
    wavelength = LIGHT_SPEED / c["frequency_hz"]
    diameter = c["rx_diameter_m"]
    beamwidth_deg = 70 * wavelength / diameter
    peak_gain_dbi = 10 * math.log10(c["efficiency"] * (math.pi * diameter / wavelength)**2)
    # Gaussian main-lobe approximation, full 3 dB beamwidth in degrees.
    pointing_loss_db = 12 * (c["pointing_deg"] / beamwidth_deg)**2
    inputs = LinkInputs(
        Terminal("sat", 0, 0, 0), Terminal("terminal", 0, 0, 0, system_noise_temp_k=c["noise_k"]),
        Scenario("Ku service link", "downlink", c["frequency_hz"], c["bandwidth_hz"],
                 "RHCP", "cn0_dbhz", 0.),
        ParametricAntenna(c["tx_gain_dbi"]), ParametricAntenna(peak_gain_dbi - pointing_loss_db),
        FreeSpacePropagation(), RFChainModel(c["tx_w"], c["feeder_loss_db"], 0.)
    )
    snapshot = ENGINE.evaluate_snapshot(elevation_deg, azimuth_deg, range_m, inputs, PropagationConditions())
    result["cn0_dbhz"] = float(snapshot.cn0_dbhz)
    for name in c["modes"]:
        mode, modem = fixed_modem(name)
        nominal_rate = c["bandwidth_hz"] * mode.net_spectral_eff_bps_per_hz()
        ebn0_db = snapshot.cn0_dbhz - 10 * math.log10(nominal_rate)
        perf = modem.throughput_mbps(ebn0_db, c["bandwidth_hz"], time_s)
        # BLER-adjusted rate; no second random radio loss in the network model.
        rate = round(1e6 * perf["throughput_mbps"])
        if rate > result["rate_bps"]:
            result.update(rate_bps=rate, modcod=name, bler=float(perf["bler_est"]), ebn0_db=float(ebn0_db))
    return result
