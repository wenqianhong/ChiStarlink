"""Decode one service-link engineering record."""


def decode(record):
    if "legacy" in record:
        return record["legacy"]
    return record["usable_hz"] - record["removed_hz"]
