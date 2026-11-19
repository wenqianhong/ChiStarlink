"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"noise_mk": value * 1000}
