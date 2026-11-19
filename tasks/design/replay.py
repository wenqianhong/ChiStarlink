"""Replay a proposed design. Write fresh per-epoch evidence for ns-3."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84
from radio import DEFAULTS, evaluate

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "tasks.json").read_text())


def simulate(case_id, candidate, start_offset_s, output):
    case = DATA["cases"][case_id]
    if candidate.keys() != case["choices"].keys():
        raise ValueError("Candidate must set exactly the editable fields listed in choices")
    for key, value in candidate.items():
        if value not in case["choices"][key]:
            raise ValueError(f"Value outside engineering catalogue for {key}: {value}")
    settings = dict(DEFAULTS, **case["radio"])
    settings.update(candidate)
    station = candidate.get("station", case["station"])
    lat, lon = DATA["stations"][station]
    ts = load.timescale(builtin=True)
    tle = DATA["tle"]
    sat = EarthSatellite(tle["line1"], tle["line2"], tle["name"], ts)
    times = np.arange(case["duration_s"])
    epochs = sat.epoch + (case["start_s"] + start_offset_s + times) / 86400
    el, az, dist = (sat - wgs84.latlon(lat, lon)).at(epochs).altaz()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, time_s in enumerate(times):
        range_m = float(dist.m[i])
        phy = evaluate(settings, el.degrees[i], az.degrees[i], range_m, int(time_s))
        rows.append(dict(time_s=int(time_s), link_id="ground-downlink", utc=epochs[i].utc_iso(),
                         elevation_deg=el.degrees[i], azimuth_deg=az.degrees[i],
                         range_m=range_m, **phy))
    for filename, columns in [("radio.csv", list(rows[0])),
                              ("trace.csv", ["time_s", "link_id", "rate_bps", "delay_s"])]:
        with (output / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=DATA["cases"])
    parser.add_argument("--candidate", type=Path, help="JSON with the editable fields; default is initial")
    parser.add_argument("--start-offset-s", type=int, default=0)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    candidate = (json.loads(args.candidate.read_text()) if args.candidate
                 else DATA["cases"][args.case]["initial"])
    simulate(args.case, candidate, args.start_offset_s, args.output)


if __name__ == "__main__":
    main()
