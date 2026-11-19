"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"gain_dbd": value - 2.15}
