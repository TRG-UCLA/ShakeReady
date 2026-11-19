# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, E. Taciroglu. Part of SR-HazardMaker; see LICENSE.
"""The ShakeReady hazard-layer format: reading a value at a site, checking and summarizing a layer.

A layer is JSON (see docs/format.md):

  format          "shakeready-hazard-grid/1"
  id, title       identifier and display name
  kind            "probabilistic" (a hazard map with one or more probability levels)
                  or "scenario" (the ground motions of one computed or recorded earthquake)
  site_condition  what the values assume about the ground, in words
  units           "g"
  scale, nodata   stored integers times `scale` give the value; `nodata` marks a node with no value
  grid            lat_min, lon_min, dlat, dlon, nlat, nlon. Node-registered, stored row by row from
                  south to north, each row from west to east.
  levels          each has an id, a label, and `measures`: one array of nlat * nlon integers per
                  intensity measure, named PGA, SA0P3, SA1P0 (5% damped spectral acceleration).
  source          where the values came from

This module and docs/sr-hazard.js implement the same rules and are tested to agree.
"""
import hashlib
import json
import math
import re

FORMAT = "shakeready-hazard-grid/1"
MEASURES = ("SA1P0", "SA0P3", "PGA")
MEASURE_NAMES = {"SA1P0": "Sa(1.0 s)", "SA0P3": "Sa(0.3 s)", "PGA": "PGA"}
SCALE = 0.001          # values are stored in thousandths of g
NODATA = -1
CALIFORNIA = dict(lat_min=32.5, lat_max=42.0, lon_min=-124.5, lon_max=-114.1)
MADE_WITH = "SR-HazardMaker, made by E. Taciroglu (https://doi.org/10.5281/zenodo.24356049)"   # written into every layer


def rnd(x):
    """Round to the nearest integer, an exact half upward. The same rule is used in the browser."""
    return math.floor(x + 0.5)


def to_int(g):
    """A ground motion in g as the stored integer."""
    return int(rnd(g / SCALE))


def value_at(h, values, lat, lon):
    """Ground motion in g at (lat, lon) from one measure's array, or None.

    Bilinear interpolation between the four surrounding nodes. Nodes without a value are left out
    and the remaining weights rescaled. None outside the grid or where no surrounding node has a value.
    """
    g = h["grid"]
    x = (lon - g["lon_min"]) / g["dlon"]
    y = (lat - g["lat_min"]) / g["dlat"]
    if x < 0 or y < 0 or x > g["nlon"] - 1 or y > g["nlat"] - 1:
        return None
    i0 = min(int(x), g["nlon"] - 2)
    j0 = min(int(y), g["nlat"] - 2)
    fx, fy = x - i0, y - j0
    total = weight = 0.0
    for dj, di, w in ((0, 0, (1 - fx) * (1 - fy)), (0, 1, fx * (1 - fy)), (1, 0, (1 - fx) * fy), (1, 1, fx * fy)):
        v = values[(j0 + dj) * g["nlon"] + (i0 + di)]
        if v != h["nodata"] and w > 0:
            total += w * v
            weight += w
    if weight <= 0:
        return None
    return total / weight * h["scale"]


def summary(h):
    """Range and coverage of each measure at each level."""
    out = []
    for lv in h["levels"]:
        for m in MEASURES:
            arr = lv["measures"].get(m)
            if arr is None:
                continue
            vals = [v for v in arr if v != h["nodata"]]
            out.append({"level": lv["id"], "label": lv["label"], "measure": m, "count": len(vals), "total": len(arr),
                        "min": min(vals) * h["scale"] if vals else None, "max": max(vals) * h["scale"] if vals else None})
    return out


def check(h):
    """Return (errors, warnings). Errors make a layer unusable; warnings deserve a second look."""
    errors, warnings = [], []
    if not isinstance(h, dict) or h.get("format") != FORMAT:
        return [f'The file\'s format is "{h.get("format") if isinstance(h, dict) else None}", not "{FORMAT}".'], warnings
    for k in ("id", "title", "kind", "site_condition", "units", "scale", "nodata", "grid", "levels", "source"):
        if k not in h or h[k] == "":
            errors.append(f'"{k}" is missing.')
    if errors:
        return errors, warnings
    if h["kind"] not in ("probabilistic", "scenario"):
        errors.append('"kind" must be probabilistic or scenario.')
    if h["units"] != "g":
        errors.append("Units must be g.")
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", h["id"]):
        errors.append("The identifier may use only lower-case letters, digits, dots, hyphens and underscores.")
    g = h["grid"]
    n = g["nlat"] * g["nlon"]
    if not (g["dlat"] > 0 and g["dlon"] > 0 and g["nlat"] >= 2 and g["nlon"] >= 2):
        errors.append("The grid needs positive spacing and at least 2 by 2 nodes.")
    if not h["levels"]:
        errors.append("The layer has no levels.")
    for lv in h["levels"]:
        if "SA1P0" not in lv.get("measures", {}):
            errors.append(f'Level "{lv["id"]}" has no Sa(1.0 s), which damage estimates need.')
        for m, arr in lv.get("measures", {}).items():
            if m not in MEASURES:
                errors.append(f'"{m}" is not a recognized measure.')
            elif len(arr) != n:
                errors.append(f'Level "{lv["id"]}", {MEASURE_NAMES[m]}: {len(arr)} values, but the grid has {n} nodes.')
    if errors:
        return errors, warnings
    lat_max = g["lat_min"] + (g["nlat"] - 1) * g["dlat"]
    lon_max = g["lon_min"] + (g["nlon"] - 1) * g["dlon"]
    c = CALIFORNIA
    if lat_max < c["lat_min"] or g["lat_min"] > c["lat_max"] or lon_max < c["lon_min"] or g["lon_min"] > c["lon_max"]:
        warnings.append("The grid does not overlap California, so no structure on the ShakeReady dashboard falls inside it.")
    s = h.get("source") or {}
    for k, label in (("title", "a title"), ("publisher", "a publisher or author"), ("retrieved_utc", "the date it was obtained or made")):
        if not s.get(k):
            warnings.append(f"The source has no {label}. A layer cannot be published without saying where it came from.")
    for row in summary(h):
        if row["count"] == 0:
            errors.append(f'Level "{row["level"]}", {MEASURE_NAMES[row["measure"]]}: no node has a value.')
        elif row["min"] < 0 or row["max"] > 10:
            warnings.append(f'Level "{row["level"]}", {MEASURE_NAMES[row["measure"]]}: values run from {row["min"]:.3f} to {row["max"]:.3f} g. Check the units.')
    return errors, warnings


def validate(h):
    """Raise ValueError if the layer has errors."""
    errors, _ = check(h)
    if errors:
        raise ValueError("; ".join(errors))
    return True


def load(path):
    with open(path, encoding="utf-8") as f:
        h = json.load(f)
    if h.get("format") != FORMAT:
        raise ValueError(f"{path}: format is {h.get('format')!r}, expected {FORMAT!r}")
    return h


def serialize(layer):
    """The layer as the text of its file: compact JSON, the same text the browser app writes."""
    return json.dumps(layer, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def index_entry(layer, sha256, nbytes):
    """What a layer needs in order to be listed in a hazard repository's index.json."""
    s = layer.get("source") or {}
    return {"id": layer["id"], "title": layer["title"], "kind": layer["kind"], "file": f"hazards/{layer['id']}.json",
            "site_condition": layer["site_condition"], "description": layer.get("description", ""),
            "measures": sorted(layer["levels"][0]["measures"]),
            "levels": [{"id": lv["id"], "label": lv["label"]} for lv in layer["levels"]],
            "source": {k: s[k] for k in ("title", "publisher", "url", "doi", "version", "retrieved_utc") if s.get(k)},
            "sha256": sha256, "bytes": nbytes}
