"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"guard_slots": round(value * 1000), "slot_s": 0.001}
