"""Wind-direction and bearing helpers for the upwind fire feature.

Conventions (both in degrees clockwise from north, 0-360):
  * wind direction = the direction the wind blows FROM (meteorological), so a west wind is 270.
  * bearing        = the initial great-circle direction from a station TO a detection.
A detection is "upwind" of a station when its bearing is within +-theta of the wind-from direction.
"""
import numpy as np


def wind_from_deg(u, v):
    """Direction the wind blows FROM, degrees from north. u = eastward, v = northward component.
    Calm air (u = v = 0) has no direction and returns NaN."""
    u, v = np.asarray(u, dtype=float), np.asarray(v, dtype=float)
    deg = (270.0 - np.degrees(np.arctan2(v, u))) % 360.0
    return np.where((u == 0) & (v == 0), np.nan, deg)


def angular_diff_deg(a, b):
    """Smallest angle between two directions, 0-180, correct across the 0/360 wrap."""
    return np.abs((np.asarray(a, dtype=float) - np.asarray(b, dtype=float) + 180.0) % 360.0 - 180.0)


def initial_bearing_deg(lat1, lon1, lat2, lon2):
    """Initial great-circle bearing from point 1 to point 2, degrees from north (0-360)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2) - np.radians(lon1)
    x = np.sin(dl) * np.cos(p2)
    y = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return np.degrees(np.arctan2(x, y)) % 360.0


def bearing_via_vectors_deg(lat1, lon1, lat2, lon2):
    """Same bearing by a different method (3-D unit vectors projected on the local east/north
    axes at point 1). Used only to cross-check initial_bearing_deg."""
    def unit(lat, lon):
        la, lo = np.radians(lat), np.radians(lon)
        return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    la1, lo1 = np.radians(lat1), np.radians(lon1)
    east = np.array([-np.sin(lo1), np.cos(lo1), 0.0])
    north = np.array([-np.sin(la1) * np.cos(lo1), -np.sin(la1) * np.sin(lo1), np.cos(la1)])
    p = unit(lat2, lon2)
    return np.degrees(np.arctan2(p @ east, p @ north)) % 360.0
