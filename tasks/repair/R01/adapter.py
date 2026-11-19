def elevation_deg(value, source_unit):
    """Translate the ephemeris field for the access selector."""
    if source_unit in ("deg", "rad"):
        return value
    raise ValueError(f"Unknown angle unit: {source_unit}")
