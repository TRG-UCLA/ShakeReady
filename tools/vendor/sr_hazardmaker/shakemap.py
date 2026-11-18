"""USGS ShakeMap: grid.xml to a hazard layer.

The field names and units are read from each file. USGS has written percent of g as "pctg" and as
"%g" in different versions of the ShakeMap software, and the set and order of fields varies.
"""
import datetime
import re
import zipfile

from .grid import FORMAT, MADE_WITH, NODATA, SCALE, rnd, to_int

UNIT_TO_G = {"pctg": 0.01, "%g": 0.01, "g": 1}


def read_text(path):
    """Return (text, name) from a grid.xml file or a zip archive that holds one."""
    base = path.replace("\\", "/").rsplit("/", 1)[-1]
    if not base.lower().endswith(".zip"):
        with open(path, encoding="utf-8-sig") as f:
            return f.read(), base
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        pick = next((n for n in names if re.search(r"(^|/)grid\.xml$", n, re.I)), None) or \
            next((n for n in names if re.search(r"grid.*\.xml$", n, re.I) and not re.search("uncertainty", n, re.I)), None)
        if not pick:
            raise ValueError(f"{base} has no grid.xml inside.")
        return z.read(pick).decode("utf-8-sig"), f"{base} → {pick}"


def _unescape(s):
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")


def _attrs(head, tag):
    m = re.search("<" + tag + r"(?=[\s/>])([^>]*)>", head)
    return {k: _unescape(v) for k, v in re.findall(r'([\w:.-]+)\s*=\s*"([^"]*)"', m.group(1))} if m else {}


def parse(text, name="grid.xml"):
    a, b = text.find("<grid_data>"), text.find("</grid_data>")
    if a < 0 or b < 0 or not re.search(r"<shakemap_grid[\s>]", text[:2000]):
        raise ValueError(f"{name} is not a ShakeMap grid file. Look for the file named grid.xml among the ShakeMap's downloads.")
    head = text[:a]
    top, event, spec = _attrs(head, "shakemap_grid"), _attrs(head, "event"), _attrs(head, "grid_specification")
    fields = []
    for m in re.finditer(r"<grid_field(?=[\s/>])([^>]*)>", head):
        f = {k: _unescape(v) for k, v in re.findall(r'([\w:.-]+)\s*=\s*"([^"]*)"', m.group(1))}
        fields.append({"index": int(f["index"]), "name": f["name"], "units": (f.get("units") or "").strip()})
    col = lambda n: next((f for f in fields if f["name"].upper() == n), None)
    f_lon, f_lat = col("LON"), col("LAT")
    if not f_lon or not f_lat or not spec.get("nlon"):
        raise ValueError(f"{name}: the grid description is incomplete.")
    want = {"SA1P0": col("PSA10"), "SA0P3": col("PSA03"), "PGA": col("PGA")}
    if not want["SA1P0"]:
        raise ValueError(f"{name} has no spectral acceleration at 1.0 second (PSA10), which damage estimates need. "
                         f"Its fields are: {', '.join(f['name'] for f in fields)}.")
    want = {m: f for m, f in want.items() if f}
    factor = {}
    for m, f in want.items():
        u = re.sub(r"\s+", "", f["units"].lower())
        if u not in UNIT_TO_G:
            raise ValueError(f'{name}: {f["name"]} is in units of "{f["units"]}", which cannot be converted to g.')
        factor[m] = UNIT_TO_G[u]
    nlon, nlat = int(spec["nlon"]), int(spec["nlat"])
    lon_min, lat_min = float(spec["lon_min"]), float(spec["lat_min"])
    dlon = (float(spec["lon_max"]) - lon_min) / (nlon - 1)
    dlat = (float(spec["lat_max"]) - lat_min) / (nlat - 1)
    measures = {m: [NODATA] * (nlat * nlon) for m in want}
    i_lon, i_lat = f_lon["index"] - 1, f_lat["index"] - 1
    cols = [(m, want[m]["index"] - 1, factor[m]) for m in want]
    rows = off = 0
    for line in text[a + 11:b].split("\n"):
        line = line.strip()
        if not line:
            continue
        r = line.split()
        i = int(rnd((float(r[i_lon]) - lon_min) / dlon))
        j = int(rnd((float(r[i_lat]) - lat_min) / dlat))
        rows += 1
        if i < 0 or j < 0 or i >= nlon or j >= nlat:
            off += 1
            continue
        for m, c, k in cols:
            try:
                v = float(r[c])
            except (ValueError, IndexError):
                continue
            if v == v and v not in (float("inf"), float("-inf")):
                measures[m][j * nlon + i] = to_int(v * k)
    return {"top": top, "event": event, "spec": spec, "fields": fields, "measures": measures,
            "grid": {"lat_min": lat_min, "lon_min": lon_min, "dlat": float(f"{dlat:.8f}"), "dlon": float(f"{dlon:.8f}"), "nlat": nlat, "nlon": nlon},
            "rows": rows, "off": off, "expected": nlat * nlon, "units": {m: want[m]["units"] for m in want}}


def defaults(p):
    """Details read from the file's header."""
    ev, top = p["event"], p["top"]
    eid = ev.get("event_id") or top.get("event_id") or "event"
    day = (ev.get("event_timestamp") or "")[:10]
    scenario = (top.get("shakemap_event_type") or "").upper() == "SCENARIO"
    version = top.get("shakemap_version") or "0"
    return {
        "id": "shakemap-" + re.sub(r"[^a-z0-9._-]", "", eid.lower()) + "-v" + version,
        "title": f"M {ev.get('magnitude') or '?'} {ev.get('event_description') or eid}" + (f", {day}" if day else "") + " (USGS ShakeMap)",
        "site_condition": "Site-specific: the ShakeMap's own estimate at each place, which includes its allowance for local ground",
        "description": ("A scenario earthquake computed with ShakeMap." if scenario else
                        "A recorded earthquake: ShakeMap's estimate of the shaking, guided by instrumental records and reports where available."),
        "source": {"title": f"USGS ShakeMap for event {eid}, version {top.get('shakemap_version') or '?'}",
                   "publisher": "U.S. Geological Survey" + (f" (network {top['shakemap_originator']})" if top.get("shakemap_originator") else ""),
                   "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{eid}",
                   "version": (f"ShakeMap version {top.get('shakemap_version') or '?'}, software {top.get('code_version') or '?'}, "
                               f"processed {top.get('process_timestamp') or '?'}, status {top.get('map_status') or '?'}")},
    }


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def build(p, meta, file_name, generator="SR-HazardMaker (USGS ShakeMap grid)"):
    ev = p["event"]
    source = dict(meta.get("source") or {})
    source["event"] = {"id": ev.get("event_id"), "magnitude": _num(ev.get("magnitude")), "depth_km": _num(ev.get("depth")),
                       "latitude": _num(ev.get("lat")), "longitude": _num(ev.get("lon")), "time": ev.get("event_timestamp"),
                       "description": ev.get("event_description"),
                       "type": "scenario" if (p["top"].get("shakemap_event_type") or "").upper() == "SCENARIO" else "recorded"}
    source["input_files"] = [{"file": file_name, "rows": p["rows"], "units_in_file": p["units"]}]
    return {
        "format": FORMAT, "id": meta["id"], "title": meta["title"], "kind": "scenario", "description": meta.get("description", ""),
        "site_condition": meta["site_condition"], "units": "g", "scale": SCALE, "nodata": NODATA, "grid": p["grid"],
        "default_level": "event", "levels": [{"id": "event", "label": "Event", "measures": p["measures"]}], "source": source,
        "provenance": {"generator": generator, "made_with": MADE_WITH, "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "stored_precision_g": SCALE, "note": "Values converted to g from the units stated in the file. The whole ShakeMap grid is kept."},
    }
