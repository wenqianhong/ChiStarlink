"""Decode one service-link engineering record."""


def decode(record):
    if "legacy" in record:
        return record["legacy"]
    return record["distance_km"] * 1852
