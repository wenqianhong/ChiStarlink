"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"zenith_deg": 90 - value}
