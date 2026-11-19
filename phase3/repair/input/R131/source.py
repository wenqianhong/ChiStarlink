"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"rtt_s": 2 * value}
