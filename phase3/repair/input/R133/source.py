"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"bidirectional_ms": value * 2000}
