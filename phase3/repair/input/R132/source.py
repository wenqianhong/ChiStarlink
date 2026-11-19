"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"us": value * 1e6}
