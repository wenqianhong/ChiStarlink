"""Sensor or telemetry publisher for the migrated format."""

import math


def encode(value, ctx):
    return {"subarray_dbi": value - 10 * math.log10(4), "coherent_gain_factor": 4}
