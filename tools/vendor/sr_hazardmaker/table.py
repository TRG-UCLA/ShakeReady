"""A table of points on a regular grid (for example the output of a simulation) to a hazard layer."""
import datetime
import re

from .grid import FORMAT, NODATA, SCALE, rnd, to_int

UNITS = {"g": 1, "%g": 0.01, "cm/s²": 1 / 980.665, "m/s²": 1 / 9.80665}
UNIT_ALIASES = {"cm/s2": "cm/s²", "cm/s^2": "cm/s²", "gal": "cm/s²", "m/s2": "m/s²", "m/s^2": "m/s²", "pctg": "%g", "percent-g": "%g"}


def _is_number(s):
    try:
        v = float(s)
    except ValueError:
        return False
    return v == v and v not in (float("inf"), float("-inf"))


def read(text):
    """Return {'header', 'rows', 'guess'}: the columns, the rows, and which column is probably which."""
    lines = [l for l in re.split(r"\r?\n", text.lstrip("\ufeff")) if l.strip() != ""]
    if len(lines) < 5:
        raise ValueError("The table has too few rows.")
    delim = sorted(((d, len(lines[0].split(d))) for d in (",", "\t", ";")), key=lambda x: -x[1])[0][0]
    first = [re.sub(r'^"|"$', "", c.strip()) for c in lines[0].split(delim)]
    has_header = any(c != "" and not _is_number(c) for c in first)
    header = first if has_header else [f"column {i + 1}" for i in range(len(first))]
    rows = [l.split(delim) for l in (lines[1:] if has_header else lines)]
    low = [re.sub(r"[\s_()]", "", c.lower()) for c in header]

    def find(tests):
        for i, c in enumerate(low):
            for t in tests:
                if (c == t) if isinstance(t, str) else bool(t.search(c)):
                    return i
        return -1

    guess = {
        "lon": find(["lon", "longitude", "long", "x", "lng"]), "lat": find(["lat", "latitude", "y"]),
        "SA1P0": find(["sa1p0", "sa1.0", "sa10", "psa10", "sa1", "sa1.0s", "sa1s", re.compile(r"^p?sa\[?1(\.0+)?s?\]?$")]),
        "SA0P3": find(["sa0p3", "sa0.3", "sa03", "psa03", "sa0.3s", re.compile(r"^p?sa\[?0?\.3s?\]?$")]), "PGA": find(["pga"]),
    }
    return {"header": header, "rows": rows, "guess": guess}


def column(t, spec):
    """A column given by name or by 1-based number, as an index; -1 if not given."""
    if spec is None or spec == "":
        return -1
    if isinstance(spec, int):
        return spec
    if spec in t["header"]:
        return t["header"].index(spec)
    if re.fullmatch(r"\d+", str(spec)) and 1 <= int(spec) <= len(t["header"]):
        return int(spec) - 1
    raise ValueError(f'There is no column "{spec}". The columns are: {", ".join(t["header"])}.')


def build(t, mapping, unit, meta, generator="SR-HazardMaker (table of points)"):
    unit = UNIT_ALIASES.get(unit, unit)
    if unit not in UNITS:
        raise ValueError(f'Unknown unit "{unit}". Use one of: {", ".join(UNITS)}.')
    k = UNITS[unit]
    if mapping.get("lon", -1) < 0 or mapping.get("lat", -1) < 0 or mapping.get("SA1P0", -1) < 0:
        raise ValueError("Choose the longitude, latitude and Sa(1.0 s) columns.")
    pts = []
    for r in t["rows"]:
        if mapping["lon"] >= len(r) or mapping["lat"] >= len(r) or r[mapping["lon"]].strip() == "":
            continue
        if _is_number(r[mapping["lon"]]) and _is_number(r[mapping["lat"]]):
            pts.append((float(r[mapping["lat"]]), float(r[mapping["lon"]]), r))
    if len(pts) < 4:
        raise ValueError("Fewer than four rows have usable coordinates.")
    r6 = lambda v: rnd(v * 1e6) / 1e6
    lats = sorted({r6(p[0]) for p in pts})
    lons = sorted({r6(p[1]) for p in pts})
    if len(lats) < 2 or len(lons) < 2:
        raise ValueError("The points lie on a single line, not a grid.")
    step = lambda a: min(b - a_ for a_, b in zip(a, a[1:]))
    nlat = int(rnd((lats[-1] - lats[0]) / step(lats))) + 1
    nlon = int(rnd((lons[-1] - lons[0]) / step(lons))) + 1
    dlat = (lats[-1] - lats[0]) / (nlat - 1)
    dlon = (lons[-1] - lons[0]) / (nlon - 1)
    on_grid = lambda a, d: all(abs((v - a[0]) / d - rnd((v - a[0]) / d)) <= 0.02 for v in a)
    if not on_grid(lats, dlat) or not on_grid(lons, dlon) or nlat * nlon > 4e6:
        raise ValueError("The points do not lie on a regular grid of latitude and longitude. SR-HazardMaker needs evenly spaced "
                         "rows and columns; scattered points are not supported yet.")
    measures = {}
    for m in ("SA1P0", "SA0P3", "PGA"):
        c = mapping.get(m, -1)
        if c is None or c < 0:
            continue
        arr = [NODATA] * (nlat * nlon)
        for lat, lon, r in pts:
            cell = r[c].strip() if c < len(r) else ""
            if cell == "" or not _is_number(cell):
                continue
            arr[int(rnd((lat - lats[0]) / dlat)) * nlon + int(rnd((lon - lons[0]) / dlon))] = to_int(float(cell) * k)
        measures[m] = arr
    source = dict(meta.get("source") or {})
    source["input_files"] = [{"file": meta.get("file_name"), "rows": len(t["rows"]), "units_in_file": unit,
                              "columns": {key: t["header"][i] for key, i in mapping.items() if i is not None and i >= 0}}]
    kind = meta.get("kind", "scenario")
    return {
        "format": FORMAT, "id": meta["id"], "title": meta["title"], "kind": kind, "description": meta.get("description", ""),
        "site_condition": meta["site_condition"], "units": "g", "scale": SCALE, "nodata": NODATA,
        "grid": {"lat_min": lats[0], "lon_min": lons[0], "dlat": float(f"{dlat:.8f}"), "dlon": float(f"{dlon:.8f}"), "nlat": nlat, "nlon": nlon},
        "default_level": "level",
        "levels": [{"id": "level", "label": meta.get("level_label") or ("Event" if kind == "scenario" else "Hazard level"), "measures": measures}],
        "source": source,
        "provenance": {"generator": generator, "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "stored_precision_g": SCALE, "note": f"Values converted to g from {unit}. {len(pts):,} points placed on a {nlat} by {nlon} grid."},
    }
