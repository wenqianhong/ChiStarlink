"""Sensor or telemetry publisher for the migrated format."""

import math


def encode(value, ctx):
    return {"dbm": 10 * math.log10(value) + 30}
