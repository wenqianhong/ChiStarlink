def receiver_polarization(label):
    """Decode the manufacturer label into the native link-budget field."""
    return {"RHCP": "RHCP", "LHCP": "LHCP", "R": "LHCP", "L": "RHCP"}[label]
