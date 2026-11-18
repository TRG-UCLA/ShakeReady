# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, E. Taciroglu. Part of SR-HazardMaker; see LICENSE.
"""USGS National Seismic Hazard Model: uniform-hazard map tables to a hazard layer.

Input is the `map.csv` table of each intensity measure for one site condition, either as separate
files or inside the USGS archive (a zip with a folder per measure). Each table has a longitude
column, a latitude column, and one column of ground motion in g per return period.
"""
import datetime
import io
import os
import re
import zipfile

from .grid import FORMAT, MADE_WITH, NODATA, SCALE, rnd, to_int

BOUNDS = dict(lat_min=32.0, lat_max=42.5, lon_min=-125.0, lon_max=-113.5)     # California with a margin
LEVEL_INFO = {475: "10% probability of exceedance in 50 years", 975: "5% probability of exceedance in 50 years",
              2475: "2% probability of exceedance in 50 years", 10000: "1% probability of exceedance in 100 years"}
_KEYS = {m: re.compile(r"(^|[^a-z0-9])" + m.lower() + r"([^a-z0-9]|$)", re.I) for m in ("SA1P0", "SA0P3", "PGA")}


def r4(v):
    return rnd(v * 1e4) / 1e4


def measure_from_name(name):
    for m, rx in _KEYS.items():
        if rx.search(name):
            return m
    return None


def _file_text(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return f.read()


def _member_text(path, member):
    """One member of an archive as text. Only that member is read, however large the archive."""
    with zipfile.ZipFile(path) as z, z.open(member) as raw:
        return io.TextIOWrapper(raw, encoding="utf-8-sig", newline="").read()


def find(paths):
    """Find one table per measure among files and archives.

    Returns (groups, notes). groups maps a site-condition label to {measure: item}; an item has
    `name`, `bytes` and `read()` returning the table's text.
    """
    groups, notes = {}, []

    def put(group, measure, item):
        groups.setdefault(group, {})[measure] = item

    for path in paths:
        base = path.replace("\\", "/").rsplit("/", 1)[-1]
        if base.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
            maps = [i for i in infos if re.search(r"(^|/)map\.csv$", i.filename, re.I)]
            for info in maps:
                m = measure_from_name(info.filename)
                if not m:
                    continue
                vs = re.search(r"vs30[-_]?(\d+)", info.filename, re.I)
                put(f"Vs30 = {vs.group(1)} m/s" if vs else "from " + base, m,
                    {"name": f"{base} → {info.filename}", "bytes": info.file_size,
                     "read": (lambda path=path, member=info.filename: _member_text(path, member))})
            notes.append(f"{base}: {len(infos):,} files inside, {len(maps)} of them hazard-map tables.")
        else:
            m = measure_from_name(base)
            if m:
                put("the files you added", m, {"name": base, "bytes": os.path.getsize(path), "read": (lambda path=path: _file_text(path))})
            else:
                notes.append(f"{base}: the name does not say which measure it holds. Rename it to include SA1P0, SA0P3 or PGA.")
    return groups, notes


def parse_map_csv(text, name="table"):
    """Return ({return_period: {(lat, lon): value}}, header, rows) for the nodes inside BOUNDS."""
    nl = text.find("\n")
    header = [c.strip() for c in text[: len(text) if nl < 0 else nl].lstrip("\ufeff").rstrip("\r").split(",")]
    low = [c.lower() for c in header]
    ilon = next((i for i, c in enumerate(low) if c in ("lon", "longitude", "long", "x")), -1)
    ilat = next((i for i, c in enumerate(low) if c in ("lat", "latitude", "y")), -1)
    if ilon < 0 or ilat < 0:
        raise ValueError(f"{name}: no longitude and latitude columns. The columns are: {', '.join(header)}.")
    periods = {}
    for i, c in enumerate(header):
        try:
            rp = float(c)
        except ValueError:
            continue
        if c != "" and rp == rp and rp not in (float("inf"), float("-inf")) and rp >= 50:
            periods[int(rnd(rp))] = i
    if not periods:
        raise ValueError(f"{name}: no return-period columns. The columns are: {', '.join(header)}.")
    out = {rp: {} for rp in periods}
    rows = 0
    b = BOUNDS
    for line in text[nl + 1:].split("\n") if nl >= 0 else []:
        if len(line) < 3:
            continue
        r = line.split(",")
        lon, lat = float(r[ilon]), float(r[ilat])
        rows += 1
        if not (b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]):
            continue
        key = (r4(lat), r4(lon))
        for rp, i in periods.items():
            cell = r[i].strip() if i < len(r) else ""
            if cell not in ("", "NaN", "nan", "null"):
                out[rp][key] = float(cell)
    return out, header, rows


def defaults(group_label, names):
    """Details that can be read off the file names: release, site condition, source."""
    allnames = " ".join(names)
    r2 = re.search(r"2023[._-]?r2", allnames, re.I) is not None
    vs = re.search(r"Vs30 = (\d+)", group_label)
    sc = re.search(r"-sc([A-E]{1,2})-", allnames)
    vs = vs.group(1) if vs else None
    return {
        "id": "usgs-nshm" + ("-2023r2" if r2 else "") + (f"-vs{vs}" if vs else ""),
        "title": "USGS National Seismic Hazard Model" + (" 2023, revision 2" if r2 else "") + (f", Vs30 {vs} m/s" if vs else ""),
        "site_condition": (f"The same ground condition everywhere: Vs30 = {vs} m/s" + (f" (site class {sc.group(1)})" if sc else "")
                           + ". Local soil is not accounted for") if vs else "",
        "description": "Uniform-hazard ground motions: at each place, the shaking with the stated chance of being exceeded. Not a single earthquake.",
        "source": {"title": ("Mean Seismic Hazard Curves and Uniform-Hazard Ground Motion Values from the Revised 2023 US 50-state "
                             "National Seismic Hazard Model (CONUS.2023.R2)") if r2 else "",
                   "publisher": "U.S. Geological Survey", "version": "CONUS.2023.R2" if r2 else "",
                   "doi": "10.5066/P14VGAV4" if r2 else "", "url": "https://doi.org/10.5066/P14VGAV4" if r2 else ""},
    }


def build(items, meta, generator="SR-HazardMaker (USGS hazard-model files)"):
    """Build the layer from {measure: item} and the layer's details."""
    data = {}
    for m in ("SA1P0", "SA0P3", "PGA"):
        if m in items:
            periods, _, rows = parse_map_csv(items[m]["read"](), items[m]["name"])
            data[m] = {"periods": periods, "rows": rows}
    if "SA1P0" not in data:
        raise ValueError("The Sa(1.0 s) table is missing. Damage estimates need it.")
    periods = None
    for m in data:
        ks = list(data[m]["periods"])
        periods = ks if periods is None else [k for k in periods if k in ks]
    periods.sort()
    if not periods:
        raise ValueError("The tables share no return period.")
    lat_set, lon_set = set(), set()
    for m in data:
        for rp in periods:
            for la, lo in data[m]["periods"][rp]:
                lat_set.add(la)
                lon_set.add(lo)
    if len(lat_set) < 2 or len(lon_set) < 2:
        raise ValueError("No values fall inside the area around California.")
    lats, lons = sorted(lat_set), sorted(lon_set)
    min_step = lambda a: r4(min(b - a_ for a_, b in zip(a, a[1:])))
    dlat, dlon = min_step(lats), min_step(lons)
    nlat = int(rnd((lats[-1] - lats[0]) / dlat)) + 1
    nlon = int(rnd((lons[-1] - lons[0]) / dlon)) + 1
    on_grid = lambda a, d: all(abs((v - a[0]) / d - rnd((v - a[0]) / d)) <= 1e-3 for v in a)
    if not on_grid(lats, dlat) or not on_grid(lons, dlon):
        raise ValueError("The points do not lie on a regular grid.")
    levels = []
    for rp in periods:
        measures = {}
        for m in data:
            arr = [NODATA] * (nlat * nlon)
            for (la, lo), v in data[m]["periods"][rp].items():
                arr[int(rnd((la - lats[0]) / dlat)) * nlon + int(rnd((lo - lons[0]) / dlon))] = to_int(v)
            measures[m] = arr
        levels.append({"id": f"rp{rp}", "label": f"{rp:,}-year return period" + (f" ({LEVEL_INFO[rp]})" if rp in LEVEL_INFO else ""),
                       "return_period_years": rp, "measures": measures})
    ids = [lv["id"] for lv in levels]
    default = meta.get("default_level") if meta.get("default_level") in ids else ("rp975" if "rp975" in ids else ids[0])
    source = dict(meta.get("source") or {})
    source["input_files"] = [{"measure": m, "file": items[m]["name"], "bytes": items[m]["bytes"], "rows": data[m]["rows"]} for m in data]
    return {
        "format": FORMAT, "id": meta["id"], "title": meta["title"], "kind": "probabilistic", "description": meta.get("description", ""),
        "site_condition": meta["site_condition"], "units": "g", "scale": SCALE, "nodata": NODATA,
        "grid": {"lat_min": lats[0], "lon_min": lons[0], "dlat": dlat, "dlon": dlon, "nlat": nlat, "nlon": nlon},
        "default_level": default, "levels": levels, "source": source,
        "provenance": {"generator": generator, "made_with": MADE_WITH, "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "cropped_to": BOUNDS, "stored_precision_g": SCALE},
    }
