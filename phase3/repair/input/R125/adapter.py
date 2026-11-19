"""Decode one service-link engineering record."""


def decode(record):
    if "legacy" in record:
        return record["legacy"]
    return record["bits_per_slot"] * 1000 / record["frame_ms"]
