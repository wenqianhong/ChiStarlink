"""Select the attenuation of the enabled RF switch path."""


def decode(record):
    if "legacy" in record:
        return record["legacy"]
    return record["isolated_dB"]
