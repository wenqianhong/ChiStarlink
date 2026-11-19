"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"feed_index": {"H": 0, "V": 1}[value]}
