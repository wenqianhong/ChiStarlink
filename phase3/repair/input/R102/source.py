"""Sensor or telemetry publisher for the migrated format."""

import math


def encode(value, ctx):
    return {"angle_rad": math.radians(value)}
