"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"decimal_kbps": value / 1000}
