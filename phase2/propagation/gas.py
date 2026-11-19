"""ITU-R P.676-12, Annex 2, slant-path attenuation in the integrated-vapour branch."""
import math
from functools import lru_cache

from itur.models import itu676


@lru_cache(maxsize=8192)
def gas_loss_db(frequency_hz, elevation_deg, pressure_hpa=1013.25, temperature_k=288.15,
                water_vapour_density_g_m3=7.5, integrated_water_kg_m2=15.0, station_height_km=0.0):
    """Return positive attenuation in dB for a visible clear-sky Earth-space path."""
    inputs = (frequency_hz, elevation_deg, pressure_hpa, temperature_k, water_vapour_density_g_m3,
              integrated_water_kg_m2, station_height_km)
    if not all(math.isfinite(value) for value in inputs):
        raise ValueError("Atmosphere and geometry must be finite")
    if not 1e9 <= frequency_hz <= 350e9 or not 5 <= elevation_deg <= 90:
        raise ValueError("P.676-12 Annex 2 requires 1–350 GHz and 5–90 degrees here")
    if min(pressure_hpa, temperature_k) <= 0 or min(water_vapour_density_g_m3, integrated_water_kg_m2) < 0:
        raise ValueError("Invalid pressure, temperature or water content")
    if itu676.get_version() != 12:
        raise RuntimeError("Pinned P.676-12 model is required")
    return float(itu676.gaseous_attenuation_slant_path(
        f=frequency_hz / 1e9, el=elevation_deg, rho=water_vapour_density_g_m3, P=pressure_hpa,
        T=temperature_k, V_t=integrated_water_kg_m2, h=station_height_km, mode="approx",
    ).value)
