"""Single serving downlink: aperture -> native RF budget -> ITU gas -> measured NR."""
import math
from functools import lru_cache

from opensatcom.antenna.parametric import ParametricAntenna
from opensatcom.core.models import LinkInputs, RFChainModel, Terminal, Scenario, PropagationConditions
from opensatcom.link.engine import DefaultLinkEngine
from opensatcom.propagation.fspl import FreeSpacePropagation
from phase2.propagation.gas import gas_loss_db
from phase2.cases.nr import select_profile

C = 299792458.0
ENGINE = DefaultLinkEngine()
DEFAULT = dict(frequency_hz=12e9, bandwidth_hz=1e6, tx_w=2.0, feeder_loss_db=1.5,
               tx_gain_dbi=16., rx_diameter_m=0.22, efficiency=0.6, noise_k=290.,
               pointing_deg=0.2, min_elev_deg=10., mcs=[4,8,12,14,16,18,20,26])


@lru_cache(maxsize=8192)
def gas(frequency_hz, elevation_deg):
    return float(gas_loss_db(frequency_hz, elevation_deg))


def rf_budget(config, elevation_deg, azimuth_deg, range_m):
    c = {**DEFAULT, **config}
    wavelength = C / c["frequency_hz"]
    d = c["rx_diameter_m"]
    peak_gain = 10 * math.log10(c["efficiency"] * (math.pi * d / wavelength)**2)
    beamwidth = 70 * wavelength / d
    pointing_loss = 12 * (c["pointing_deg"] / beamwidth)**2
    inputs = LinkInputs(
        Terminal("sat", 0, 0, 0), Terminal("ground", 0, 0, 0, system_noise_temp_k=c["noise_k"]),
        Scenario("service", "downlink", c["frequency_hz"], c["bandwidth_hz"], "RHCP", "cn0_dbhz", 0.),
        ParametricAntenna(c["tx_gain_dbi"]), ParametricAntenna(peak_gain - pointing_loss),
        FreeSpacePropagation(), RFChainModel(c["tx_w"], c["feeder_loss_db"], 0.))
    rf = ENGINE.evaluate_snapshot(elevation_deg, azimuth_deg, range_m, inputs, PropagationConditions())
    gas_db = gas(c["frequency_hz"], elevation_deg)
    return {"tx_w":c["tx_w"], "rx_peak_gain_dbi":peak_gain,
            "rx_pointing_loss_db":pointing_loss,"cn0_free_space_dbhz":float(rf.cn0_dbhz),
            "gas_db":gas_db,"cn0_dbhz":float(rf.cn0_dbhz)-gas_db}


def evaluate(config, elevation_deg, azimuth_deg, range_m, time_s):
    c = {**DEFAULT, **config}
    result = dict(time_s=time_s, delay_s=range_m / C, range_m=range_m, elevation_deg=elevation_deg,
                  rate_bps=0, cn0_dbhz=None, gas_db=None, mcs=None, prbs=None, bler=None)
    if elevation_deg < c["min_elev_deg"]:
        return result
    rf = rf_budget(c, elevation_deg, azimuth_deg, range_m)
    phy = select_profile(rf["cn0_dbhz"], c["bandwidth_hz"], c["mcs"])
    return {**result, **rf, **phy}
