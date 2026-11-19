def service_rate_bps(value, source_unit):
    """Export the modem's service-rate field to the ns-3 trace."""
    factors = {"Mbit/s": 1_000_000, "kbit/s": 1}
    return round(value * factors[source_unit])
