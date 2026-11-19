"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"installed_w": value / 0.8, "reserved": 0.2}
