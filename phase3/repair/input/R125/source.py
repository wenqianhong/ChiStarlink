"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"bits_per_slot": value / 1000, "slot_ms": 1, "frame_ms": 10}
