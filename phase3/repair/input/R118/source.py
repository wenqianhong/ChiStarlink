"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"word": value / 1e8, "step_hz": 1e8}
