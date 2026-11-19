"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"bytes_per_s": value / 8}
