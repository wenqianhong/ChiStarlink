"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"tenths_deg": round(value * 10)}
