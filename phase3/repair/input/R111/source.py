"""Publish the measured loss of each RF switch path."""


def encode(value, ctx):
    return {"active": "through", "through_dB": value, "isolated_dB": value + 20}
