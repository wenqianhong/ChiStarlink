"""Map a post-propagation C/N0 to a measured, one-layer NR downlink transport rate."""
import csv
import math
from bisect import bisect_left
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

CURVES = Path(__file__).resolve().parents[1] / "oai" / "curves.csv"


@lru_cache(maxsize=4)
def read_curves(filename):
    grouped = defaultdict(list)
    with Path(filename).open() as source:
        for row in csv.DictReader(source):
            allocation = (int(row["prbs"]), int(row["mcs"]), int(row["scs_hz"]),
                          float(row["slot_s"]), int(row["tbs_bits"]))
            snr = float(row["snr_db"])
            trials, errors = int(row["trials"]), int(row["errors"])
            if trials < 1 or not 0 <= errors <= trials:
                raise ValueError(f"Invalid empirical counts in {filename}: {row}")
            bler = errors / trials
            if not math.isclose(bler, float(row["bler"]), abs_tol=1e-5):
                raise ValueError("BLER disagrees with measured transport-block counts")
            grouped[allocation].append((snr, bler, errors, trials))
    if not grouped:
        raise ValueError(f"No empirical OAI points in {filename}")
    for points in grouped.values():
        points.sort()
        if len(set(p[0] for p in points)) != len(points):
            raise ValueError("Duplicate SNR for the same resource allocation")
    return grouped


def select_profile(cn0_dbhz, bandwidth_hz, mcs_allowed, curve_file=None):
    curves = read_curves(str(curve_file or CURVES))
    allowed = set(mcs_allowed)
    profiles = [p for p in curves if p[1] in allowed and p[0]*12*p[2] <= bandwidth_hz]
    if not profiles:
        raise ValueError(f"No measured resource allocation fits {bandwidth_hz} Hz and MCS {allowed}")
    # Use the largest measured allocation that fits the budget, then choose MCS by expected goodput.
    occupied = max(p[0]*12*p[2] for p in profiles)
    snr = cn0_dbhz - 10 * math.log10(occupied)
    choices = []
    for profile in profiles:
        prbs, mcs, scs, slot, tbs = profile
        if prbs*12*scs != occupied:
            continue
        points = curves[profile]
        if not points[0][0] <= snr <= points[-1][0]:
            continue
        right = bisect_left([p[0] for p in points], snr)
        high = points[right]
        low = high if high[0] == snr else points[right-1]
        weight = (snr - low[0]) / (high[0] - low[0]) if high[0] > low[0] else 0
        bler = low[1] + weight * (high[1] - low[1])
        rate = round(tbs / slot * (1 - bler))
        choices.append(dict(rate_bps=rate, mcs=mcs, prbs=prbs, tbs_bits=tbs, slot_s=slot,
                            scs_hz=scs, occupied_bw_hz=occupied, snr_db=snr, bler=bler,
                            lower_snr_db=low[0], upper_snr_db=high[0], lower_errors=low[2],
                            lower_trials=low[3], upper_errors=high[2], upper_trials=high[3]))
    if not choices:
        raise ValueError(f"SNR {snr:.3f} dB outside all measured curves for {occupied} Hz, MCS {allowed}")
    return max(choices, key=lambda row: (row["rate_bps"], -row["mcs"]))
