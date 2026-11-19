"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"centidb": value * 100}
