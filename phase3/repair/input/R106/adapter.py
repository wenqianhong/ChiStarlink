"""Decode one service-link engineering record."""


def decode(record):
    if "legacy" in record:
        return record["legacy"]
    return 10 ** ((record["dbm"] - 60) / 10)
