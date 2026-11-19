"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"system_k": value, "included_frontend_k": 0.9 * value}
