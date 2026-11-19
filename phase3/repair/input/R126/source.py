"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"reserved_fraction": 1 - value}
