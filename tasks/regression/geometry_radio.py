"""Compute the routed satellite's downlink using source TLEs and OpenSatCom."""
import json
import sys

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84

from radio import evaluate

data = json.load(sys.stdin)
ts = load.timescale(builtin=True)
lat, lon, elev = data["station"]
station = wgs84.latlon(lat, lon, elevation_m=elev)
samples = data["samples"]
for sid in {s["route"][-2] for s in samples}:
    name, line1, line2 = data["tle"][3 * sid:3 * sid + 3]
    satellite = EarthSatellite(line1, line2, name, ts)
    subset = [s for s in samples if s["route"][-2] == sid]
    times = np.array([s["time_s"] for s in subset])
    el, az, ranges = (satellite - station).at(satellite.epoch + times / 86400).altaz()
    for i, sample in enumerate(subset):
        meters = float(ranges.m[i])
        elevation = float(el.degrees[i])
        sample.update(range_m=meters, elevation_deg=elevation,
                      **evaluate(data["config"], elevation, float(az.degrees[i]), meters, sample["time_s"]))
json.dump(samples, sys.stdout, allow_nan=False)
