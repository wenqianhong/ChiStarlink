"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"policy": {"active": list(value), "fallback": [4]}}
