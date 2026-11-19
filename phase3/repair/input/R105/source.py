"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"distance_km": value / 1000}
