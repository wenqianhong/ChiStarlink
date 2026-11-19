"""Inside the ITU/OpenSatCom image: evaluate active satellites in a single batch."""
import json
import math
import sys

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84
from phase2.cases.radio import evaluate, rf_budget


def run(job):
    target = wgs84.latlon(*job["station"][:2], elevation_m=job["station"][2])
    samples = job["samples"]
    ts = load.timescale(builtin=True)
    for sat_id in sorted({s["sat_id"] for s in samples}):
        name, l1, l2 = job["tle"][sat_id*3:sat_id*3+3]
        sat = EarthSatellite(l1,l2,name,ts)
        group = [s for s in samples if s["sat_id"] == sat_id]
        t = sat.epoch + np.array([s["orbit_s"] for s in group]) / 86400.
        el, az, ranges = (sat-target).at(t).altaz()
        for index, sample in enumerate(group):
            elevation, azimuth, dist = float(el.degrees[index]), float(az.degrees[index]), float(ranges.m[index])
            sample.update(utc=t[index].utc_iso(), azimuth_deg=azimuth,
                          **evaluate(job["config"], elevation, azimuth, dist, sample["time_s"]))
    return samples


def aperture_check():
    # Independent analytical oracle: the area ratio is four. At boresight all other link terms cancel.
    common = {"tx_w":2., "pointing_deg":0.}
    def budget(diameter, pointing):
        return rf_budget({**common, "rx_diameter_m":diameter,"pointing_deg":pointing}, 26.,0.,1228000.)
    delta = budget(.22,0)["cn0_dbhz"]-budget(.11,0)["cn0_dbhz"]
    actual = budget(.22,.2)["cn0_dbhz"]-budget(.11,.2)["cn0_dbhz"]
    ideal = 10 * math.log10(4)
    assert abs(delta - ideal) < 1e-9
    assert abs(delta - actual) < .02
    return {"expected_boresight_db":ideal,"measured_boresight_db":delta,
            "measured_with_tracking_db":actual,"boresight_tolerance_db":1e-9,"passed":True}


if __name__ == "__main__":
    job = json.load(sys.stdin)
    data = aperture_check() if job.get("aperture_check") else run(job)
    print(json.dumps(data,allow_nan=False))
