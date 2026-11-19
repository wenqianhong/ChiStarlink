"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"usable_hz": value, "removed_hz": 540000}
