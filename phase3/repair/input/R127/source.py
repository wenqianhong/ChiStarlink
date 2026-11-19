"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"period_slots": 10, "idle_slots": round(10 * (1 - value))}
