"""Decode one service-link engineering record."""


def decode(record):
    if "legacy" in record:
        return record["legacy"]
    return {"R": "LHCP", "L": "RHCP"}[record["circular"]]
