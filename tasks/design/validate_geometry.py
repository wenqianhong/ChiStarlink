"""Check Skyfield slant ranges against Hypatia's original satgenpy function."""
import argparse
import importlib.util
import json
from pathlib import Path

import ephem
import numpy as np
from skyfield.api import EarthSatellite, load, wgs84

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "tasks.json").read_text())


def validate(hypatia):
    native_file = hypatia / "satgenpy/satgen/distance_tools/distance_tools.py"
    spec = importlib.util.spec_from_file_location("upstream_distance", native_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = hypatia / "paper/satellite_networks_state/input_data/legacy/starlink_tles_25x25.txt"
    lines = path.read_text().splitlines()[1:4]
    assert lines == [MANIFEST["tle"][key] for key in ("name", "line1", "line2")]
    native_sat = ephem.readtle(*lines)
    ts = load.timescale(builtin=True)
    sky_sat = EarthSatellite(lines[1], lines[2], lines[0], ts)
    errors = []
    for case in MANIFEST["cases"].values():
        for lat, lon in MANIFEST["stations"].values():
            station = {"latitude_degrees_str":str(lat), "longitude_degrees_str":str(lon),
                       "elevation_m_float":0.}
            observer = sky_sat - wgs84.latlon(lat, lon)
            for index in range(case["duration_s"]):
                t = sky_sat.epoch + (case["start_s"] + index) / 86400
                current = t.utc_datetime().replace(tzinfo=None)
                native_range = module.distance_m_ground_station_to_satellite(
                    station, native_sat, sky_sat.epoch.utc_datetime().replace(tzinfo=None), current)
                dist = observer.at(t).distance().m
                errors.append(abs(native_range - dist))
    # Different SGP4 implementations and observer ellipsoids; budget 0.01 ms one-way.
    worst = max(errors)
    tolerance = 0.00001 * 299792458.0
    result = {"samples":len(errors), "max_absolute_range_difference_m":float(worst),
              "mean_absolute_range_difference_m":float(np.mean(errors)),
              "range_tolerance_m":tolerance, "passed":bool(worst < tolerance)}
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("hypatia", type=Path)
    result = validate(p.parse_args().hypatia)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
