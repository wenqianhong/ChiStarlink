"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"echo_path_m": value * 2}
