"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"pa_mw": value * 1000}
