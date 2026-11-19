"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"steps": value * 4, "step_db": 0.25}
