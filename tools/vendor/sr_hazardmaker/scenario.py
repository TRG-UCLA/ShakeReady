# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, E. Taciroglu. Part of SR-HazardMaker; see LICENSE.
"""Scenario builder: the shaking of a described earthquake, computed with a ground-motion model.

The earthquake is described by its magnitude, its style of faulting, and its rupture: a straight
fault trace between two points, a dip, and, for a dipping fault, a down-dip width. The ground is
described by one Vs30 used everywhere. The result is a scenario hazard layer.

docs/scenario.js holds the same builder for the browser; the two are tested to give the same layer.
"""
import datetime
import math
import re

from . import bssa14
from .grid import FORMAT, MADE_WITH, NODATA, SCALE, rnd, to_int

R_EARTH_KM = 6371.0
MEASURES = ("SA1P0", "SA0P3", "PGA")
DEFAULTS = {"dip": 90.0, "width_km": 15.0, "vs30": 760.0, "epsilon": 0.0, "spacing": 0.02, "margin_km": 100.0}
MAX_NODES = 400000


def num(x):
    """A number as text, the same way in Python and in the browser: 7.0 -> '7', 6.5 -> '6.5'."""
    x = float(x)
    return str(int(x)) if x == int(x) and abs(x) < 1e15 else repr(x)


POINT_HELP = "Give a latitude and a longitude, for example 34.40, -118.80. West longitudes are negative."


def parse_point(text):
    """A point as a person writes it, as [latitude, longitude].

    Accepts '34.40, -118.80', '34.40 -118.80', '34.40 N, 118.80 W' and '118.80W 34.40N', with or
    without degree signs, and the minus sign that word processors substitute for a hyphen.
    """
    s = str(text)
    for a, b in (("\u2212", "-"), ("\u2013", "-"), ("\u2014", "-"), ("\u00b0", " "), ("\u00ba", " ")):
        s = s.replace(a, b)
    found = re.findall(r"([-+]?\d+(?:\.\d+)?)\s*([NSEWnsew]?)", s)
    if len(found) != 2:
        raise ValueError(POINT_HELP)
    vals = []
    for number, letter in found:
        v, letter = float(number), letter.upper()
        if letter in ("S", "W") and v > 0:
            v = -v
        vals.append((v, letter))
    (a, la), (b, lb) = vals
    if la in ("E", "W") or lb in ("N", "S"):          # written longitude first
        a, b = b, a
    return [a, b]


def check_params(p):
    """Fill in defaults, check ranges, and return the complete description of the scenario."""
    q = dict(DEFAULTS)
    q.update({k: v for k, v in p.items() if v is not None and v != ""})
    for key in ("magnitude", "mechanism", "trace"):
        if key not in q:
            raise ValueError(f"The scenario needs a {key}.")
    for key in ("magnitude", "dip", "width_km", "vs30", "epsilon", "spacing", "margin_km"):
        q[key] = float(q[key])
        if q[key] != q[key]:
            raise ValueError(f"{key} is not a number.")
    trace = [[float(q["trace"][0][0]), float(q["trace"][0][1])], [float(q["trace"][1][0]), float(q["trace"][1][1])]]
    for lat, lon in trace:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Each end of the fault needs a latitude from -90 to 90 and a longitude from -180 to 180.")
    q["trace"] = trace
    bssa14.check_inputs(q["magnitude"], q["mechanism"], q["vs30"])
    if not (0 < q["dip"] <= 90):
        raise ValueError("The dip must be more than 0 and at most 90 degrees.")
    if not (0 < q["width_km"] <= 60):
        raise ValueError("The down-dip width must be more than 0 and at most 60 km.")
    if not (-3 <= q["epsilon"] <= 3):
        raise ValueError("Epsilon must be between -3 and 3 standard deviations.")
    if not (0.005 <= q["spacing"] <= 0.25):
        raise ValueError("The grid spacing must be between 0.005 and 0.25 degrees.")
    if not (10 <= q["margin_km"] <= 250):
        raise ValueError("The margin around the fault must be between 10 and 250 km.")
    geometry(q)                      # refuses a fault with no length
    return q


def geometry(p):
    """The rupture's surface projection in a flat local frame centered on the fault trace (km)."""
    (lat_a, lon_a), (lat_b, lon_b) = p["trace"]
    lat0, lon0 = (lat_a + lat_b) / 2, (lon_a + lon_b) / 2
    ky = R_EARTH_KM * math.pi / 180.0
    kx = ky * math.cos(lat0 * (math.pi / 180.0))
    ax, ay = (lon_a - lon0) * kx, (lat_a - lat0) * ky
    bx, by = (lon_b - lon0) * kx, (lat_b - lat0) * ky
    length = math.sqrt((bx - ax) * (bx - ax) + (by - ay) * (by - ay))
    if length < 0.1:
        raise ValueError("The two ends of the fault are the same point.")
    ux, uy = (bx - ax) / length, (by - ay) / length
    # the fault dips to the right of the direction from its first end to its second
    w = p["width_km"] * math.cos(p["dip"] * (math.pi / 180.0)) if p["dip"] < 90 else 0.0
    return {"lat0": lat0, "lon0": lon0, "kx": kx, "ky": ky, "ax": ax, "ay": ay, "ux": ux, "uy": uy, "nx": uy, "ny": -ux, "length": length, "w": w}


def rjb(g, lat, lon):
    """Joyner-Boore distance in km: the horizontal distance to the surface projection of the rupture."""
    px, py = (lon - g["lon0"]) * g["kx"] - g["ax"], (lat - g["lat0"]) * g["ky"] - g["ay"]
    s = px * g["ux"] + py * g["uy"]
    t = px * g["nx"] + py * g["ny"]
    ds = -s if s < 0 else (s - g["length"] if s > g["length"] else 0.0)
    dt = -t if t < 0 else (t - g["w"] if t > g["w"] else 0.0)
    return math.sqrt(ds * ds + dt * dt)


def grid_for(p, g):
    """A grid covering the rupture's surface projection plus the margin, snapped to multiples of the spacing."""
    sp = p["spacing"]
    corners = [(g["ax"], g["ay"]), (g["ax"] + g["ux"] * g["length"], g["ay"] + g["uy"] * g["length"])]
    corners += [(x + g["nx"] * g["w"], y + g["ny"] * g["w"]) for x, y in corners]
    lats = [g["lat0"] + y / g["ky"] for _, y in corners]
    lons = [g["lon0"] + x / g["kx"] for x, _ in corners]
    j0 = math.floor((min(lats) - p["margin_km"] / g["ky"]) / sp)
    j1 = math.ceil((max(lats) + p["margin_km"] / g["ky"]) / sp)
    i0 = math.floor((min(lons) - p["margin_km"] / g["kx"]) / sp)
    i1 = math.ceil((max(lons) + p["margin_km"] / g["kx"]) / sp)
    nlat, nlon = j1 - j0 + 1, i1 - i0 + 1
    if nlat * nlon > MAX_NODES:
        raise ValueError(f"That would be a grid of {nlat * nlon:,} points. Use a coarser spacing or a smaller margin.")
    return {"lat_min": rnd(j0 * sp * 1e6) / 1e6, "lon_min": rnd(i0 * sp * 1e6) / 1e6, "dlat": sp, "dlon": sp, "nlat": nlat, "nlon": nlon}


def surface_projection(g):
    """The corners of the rupture's footprint at the surface, as [latitude, longitude]: the two ends of the
    trace, then the same two ends carried down dip. None for a vertical fault, whose footprint is its trace."""
    if g["w"] <= 0:
        return None
    a = (g["ax"], g["ay"])
    b = (g["ax"] + g["ux"] * g["length"], g["ay"] + g["uy"] * g["length"])
    corners = [a, b, (b[0] + g["nx"] * g["w"], b[1] + g["ny"] * g["w"]), (a[0] + g["nx"] * g["w"], a[1] + g["ny"] * g["w"])]
    return [[rnd((g["lat0"] + y / g["ky"]) * 1e5) / 1e5, rnd((g["lon0"] + x / g["kx"]) * 1e5) / 1e5] for x, y in corners]


def level_label(epsilon):
    if epsilon == 0:
        return "Median"
    return f"Median {'plus' if epsilon > 0 else 'minus'} {num(abs(epsilon))} standard deviation" + ("" if abs(epsilon) == 1 else "s")


def defaults(p):
    """The layer's details as they follow from the scenario; the maker's name still has to be given."""
    p = check_params(p)
    g = geometry(p)
    (lat_a, lon_a), (lat_b, lon_b) = p["trace"]
    shape = "vertical" if p["dip"] >= 90 else f"dipping {num(p['dip'])} degrees with a down-dip width of {num(p['width_km'])} km"
    title = f"M {num(p['magnitude'])} {p['mechanism']} scenario earthquake"
    return {
        "title": title,
        "site_condition": f"The same ground condition everywhere: Vs30 = {num(p['vs30'])} m/s. Local soil is not accounted for",
        "description": (f"{level_label(p['epsilon'])} ground motions of a magnitude {num(p['magnitude'])} earthquake, {p['mechanism']} faulting, on a fault "
                        f"from ({lat_a:.4f}, {lon_a:.4f}) to ({lat_b:.4f}, {lon_b:.4f}), {g['length']:.1f} km long, {shape}. Computed with a "
                        "ground-motion model, not recorded."),
        "source": {"title": f"Scenario computed with SR-HazardMaker using the ground-motion model of {bssa14.NAME}", "publisher": "",
                   "version": "BSSA14 base model: no regional adjustment, no basin term; RotD50 horizontal component"},
    }


def build(p, meta, generator="SR-HazardMaker (scenario builder)"):
    """Compute the scenario and return it as a hazard layer."""
    p = check_params(p)
    g = geometry(p)
    grid = grid_for(p, g)
    nlat, nlon = grid["nlat"], grid["nlon"]
    measures = {m: [NODATA] * (nlat * nlon) for m in MEASURES}
    for j in range(nlat):
        lat = grid["lat_min"] + j * grid["dlat"]
        for i in range(nlon):
            r = rjb(g, lat, grid["lon_min"] + i * grid["dlon"])
            for m in MEASURES:
                measures[m][j * nlon + i] = to_int(bssa14.ground_motion(m, p["magnitude"], p["mechanism"], r, p["vs30"], p["epsilon"]))
    source = dict(meta.get("source") or {})
    source["scenario"] = {
        "magnitude": p["magnitude"], "mechanism": p["mechanism"], "trace": p["trace"], "length_km": float(f"{g['length']:.3f}"),
        "dip_deg": p["dip"], "down_dip_width_km": p["width_km"], "vs30_m_per_s": p["vs30"], "epsilon": p["epsilon"],
        "model": bssa14.CITATION, "model_options": "base model: no regional adjustment, no basin term", "component": "RotD50",
        "distance": "Joyner-Boore distance to the surface projection of a planar rectangular rupture, in a flat local frame"}
    footprint = surface_projection(g)
    if footprint:
        source["scenario"]["surface_projection"] = footprint
    return {
        "format": FORMAT, "id": meta["id"], "title": meta["title"], "kind": "scenario", "description": meta.get("description", ""),
        "site_condition": meta["site_condition"], "units": "g", "scale": SCALE, "nodata": NODATA, "grid": grid, "default_level": "event",
        "levels": [{"id": "event", "label": level_label(p["epsilon"]), "measures": measures}], "source": source,
        "provenance": {"generator": generator, "made_with": MADE_WITH, "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "stored_precision_g": SCALE,
                       "note": ("Computed, not recorded. One Vs30 is used everywhere. With epsilon other than zero, every point is shifted by the same number "
                                "of standard deviations, which is not a simulated realization of the event.")},
    }
