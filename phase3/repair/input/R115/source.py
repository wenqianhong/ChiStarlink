"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"circular": value[0]}
