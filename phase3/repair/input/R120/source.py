"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"groups": value / (2 * 180000), "prbs_per_group": 2}
