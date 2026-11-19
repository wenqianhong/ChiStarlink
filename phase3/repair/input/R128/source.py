"""Sensor or telemetry publisher for the migrated format."""


def encode(value, ctx):
    return {"nominal_bps": ctx["nominal_bps"], "bler": ctx["bler"]}
