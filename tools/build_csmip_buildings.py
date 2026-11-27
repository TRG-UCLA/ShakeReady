#!/usr/bin/env python3
"""Build the CSMIP Instrumented Buildings inventory from the two layers rescued from the original site.

Part of ShakeReady. Made by E. Taciroglu.

Inputs, kept in the repository unchanged:
    data/instrumented_buildings.geojson               55 buildings
    data/instrumented_nonductile_buildings.geojson     6 buildings, listed apart by the original team as non-ductile
Output:
    data/csmip_instrumented_buildings.geojson         61 buildings in one inventory, with one set of attributes

All 61 are stations of the California Strong Motion Instrumentation Program (CSMIP): every station page linked from
the two files is a CESMD page of the CGS network. No station is in both files, and the script stops if one ever is.

What the script does, and nothing else (decisions BLD-08 to BLD-10 on the Methods page):

  * Gives every building the same attributes. The two files named two things differently: the 55 keep the station
    name in "Station" and the address in "name"; the 6 keep the station name in "name" and the address in "Address".
    Here "name" is the station name and "address" the address, for all 61.
  * Records which file a building came from, in "original_layer", so the six can still be told apart.
  * Brings the six's number formats and one spelling in line with the 55: stories "12.0" becomes "12", basements
    "2.0" becomes "2", and the plan shape written '"L" Shape' becomes "L-shaped". Every such change is listed when
    the script runs. No other recorded value is altered.
  * Adds values read out of the recorded text, so that they can be filtered on: "station_number" from the station
    page's address; "stories" (the leading whole number of "Num of Stories"); "design_year" (the first year in
    "Design Date"); and from "Instrumentation" the year, the number of accelerometers in the building, the number
    of instrumented levels, and whether a free-field site is mentioned. The text itself is kept beside them.

Positions are the two files' own. Attributes that only repeat the position or the layer are not carried
("Latitude", "Longitude", "coord_source", "address_kml", "layer", "Station"); they remain in the two input files.

Run from the repository root:  python3 tools/build_csmip_buildings.py
"""
import collections
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERAL = os.path.join(ROOT, "data", "instrumented_buildings.geojson")
NONDUCTILE = os.path.join(ROOT, "data", "instrumented_nonductile_buildings.geojson")
OUT = os.path.join(ROOT, "data", "csmip_instrumented_buildings.geojson")

TITLE = "CSMIP Instrumented Buildings"
PLAN_SPELLING = {'"L" Shape': "L-shaped"}          # the six's spelling -> the spelling the 55 use for the same shape
AS_RECORDED = ("Elevation (m)", "Num of Stories", "Basement", "Plan Shape", "Base Dimensions", "Typical Floor Dimensions",
               "Design Date", "Instrumentation", "Information", "images")
ATTRIBUTES = {
    "name": "Station name, as recorded.",
    "address": "Street address, as recorded.",
    "station_number": "CSMIP station number, read from the address of the station page (the digits after staID=CE).",
    "original_layer": "The layer of the original ShakeReady site the building came from. The six from 'Instrumented Non-Ductile Buildings' were listed apart by the original team as non-ductile concrete. The other 55 were not classified, which is not a statement that they are ductile.",
    "stories": "The leading whole number of 'Num of Stories'. Blank where none is recorded.",
    "design_year": "The first year given in 'Design Date'. Where the text gives several dates, or a retrofit or strengthening date, read the text. Blank where none is recorded.",
    "instrumented_year": "The year at the start of 'Instrumentation'. Blank where none is given.",
    "accelerometers": "The number of accelerometers in the building: the first count in 'Instrumentation'. Sensors at free-field, ground, downhole or adjacent sites are not included.",
    "instrumented_levels": "The number of levels of the building with accelerometers, from 'Instrumentation'.",
    "free_field": "True where 'Instrumentation' mentions a free-field site, false where it does not, blank where there is no text.",
}
ABOUT = ("The %d instrumented buildings of the original ShakeReady site in one inventory: 55 from its 'Instrumented Buildings' layer and 6 from its "
         "'Instrumented Non-Ductile Buildings' layer, compiled in 2017 from CESMD station pages and not updated since. All are stations of the "
         "California Strong Motion Instrumentation Program. Attributes in Title Case are as recorded in those layers, except that the six's number "
         "formats and one spelling were brought in line with the other 55. Attributes in lower case were added or renamed when the two were combined; "
         "see 'attributes'. Built by tools/build_csmip_buildings.py; sources, choices and checksums are at methods.html. Part of ShakeReady.")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def whole(text):
    """'12.0' -> '12'; anything that is not a whole number written with '.0' is returned as it is."""
    if isinstance(text, str):
        m = re.fullmatch(r"\s*(\d+)\.0\s*", text)
        if m:
            return m.group(1)
    return text


def leading_int(text):
    m = re.match(r"\s*(\d+)(?!\d)", text or "")
    return int(m.group(1)) if m else None


def first_year(text):
    m = re.search(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", text or "")
    return int(m.group(1)) if m else None


def instrumentation(text):
    """(year, accelerometers in the building, levels, free field) from text such as
    '1976. 13 accelerometers, on 4 levels in the building. 3 accelerometers at a reference free-field site.'"""
    if not text:
        return None, None, None, None
    year = re.match(r"\s*((?:19|20)\d\d)\s*[.,]", text)
    acc = re.search(r"(\d+)\s+accel\w*meters?", text)            # the first count; the source also spells it "accelometers"
    lev = re.search(r"(\d+)\s+levels?", text)
    if not acc or not lev:
        raise SystemExit(f"Could not read the instrumentation text: {text!r}")
    return (int(year.group(1)) if year else None), int(acc.group(1)), int(lev.group(1)), bool(re.search(r"free[- ]field", text, re.I))


def distance_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def build():
    general, nonductile = load(GENERAL), load(NONDUCTILE)
    changes, feats = [], []
    for feature, name_key, address_key in [(f, "Station", "name") for f in general] + [(f, "name", "Address") for f in nonductile]:
        p = feature["properties"]
        if not feature.get("geometry") or feature["geometry"]["type"] != "Point":
            raise SystemExit(f"{p.get(name_key)!r} has no position.")
        station = re.search(r"staID=CE(\d+)&network=CGS", p.get("Information") or "")
        if not station:
            raise SystemExit(f"{p.get(name_key)!r}: the station page link is not a CESMD page of the CGS network: {p.get('Information')!r}")
        rec = {k: p.get(k) for k in AS_RECORDED}
        for k in ("Num of Stories", "Basement"):
            if whole(rec[k]) != rec[k]:
                changes.append((p[name_key], k, rec[k], whole(rec[k])))
                rec[k] = whole(rec[k])
        if rec["Plan Shape"] in PLAN_SPELLING:
            changes.append((p[name_key], "Plan Shape", rec["Plan Shape"], PLAN_SPELLING[rec["Plan Shape"]]))
            rec["Plan Shape"] = PLAN_SPELLING[rec["Plan Shape"]]
        year, acc, lev, free = instrumentation(rec["Instrumentation"])
        props = collections.OrderedDict()
        props["name"], props["address"] = p[name_key], p[address_key]
        props["station_number"], props["original_layer"] = station.group(1), p["layer"]
        for k in AS_RECORDED:
            props[k] = rec[k]
            if k == "Num of Stories":
                props["stories"] = leading_int(rec[k])
            elif k == "Design Date":
                props["design_year"] = first_year(rec[k])
            elif k == "Instrumentation":
                props["instrumented_year"], props["accelerometers"], props["instrumented_levels"], props["free_field"] = year, acc, lev, free
        feats.append({"type": "Feature", "geometry": feature["geometry"], "properties": props})
    feats.sort(key=lambda f: (f["properties"]["name"].lower(), f["properties"]["station_number"]))
    return general, nonductile, feats, changes


def check(general, nonductile, feats):
    """Stop unless the result is what the description above says it is. Returns facts worth printing."""
    assert len(feats) == len(general) + len(nonductile)
    numbers = [f["properties"]["station_number"] for f in feats]
    repeated = [n for n, c in collections.Counter(numbers).items() if c > 1]
    if repeated:
        raise SystemExit(f"Station number(s) {repeated} appear more than once: a building is in both files, or twice in one. Decide which record to keep before combining.")
    layers = collections.Counter(f["properties"]["original_layer"] for f in feats)
    assert layers == {"Instrumented Buildings": len(general), "Instrumented Non-Ductile Buildings": len(nonductile)}, layers
    six = [f for f in feats if f["properties"]["original_layer"] == "Instrumented Non-Ductile Buildings"]
    rest = [f for f in feats if f not in six]
    nearest = min(distance_km(a["geometry"]["coordinates"], b["geometry"]["coordinates"]) for a in six for b in rest)
    # every as-recorded value equals the input's, apart from the listed format changes; positions are untouched
    source = {re.search(r"staID=CE(\d+)", f["properties"]["Information"]).group(1): f for f in general + nonductile}
    for f in feats:
        p, s = f["properties"], source[f["properties"]["station_number"]]
        sp = s["properties"]
        assert f["geometry"] == s["geometry"]
        assert p["name"] == (sp.get("Station") or sp["name"]) and p["address"] == (sp["name"] if "Station" in sp else sp["Address"])
        for k in AS_RECORDED:
            want = sp.get(k)
            if k in ("Num of Stories", "Basement"):
                want = whole(want)
            if k == "Plan Shape":
                want = PLAN_SPELLING.get(want, want)
            assert p[k] == want, (p["name"], k, p[k], sp.get(k))
        if p["stories"] is not None:
            assert str(p["Num of Stories"]).strip().startswith(str(p["stories"]))
        if p["design_year"] is not None:
            assert str(p["design_year"]) in p["Design Date"]
    return {"nearest_km": nearest}


def main():
    general, nonductile, feats, changes = build()
    facts = check(general, nonductile, feats)
    out = collections.OrderedDict([("type", "FeatureCollection"), ("name", TITLE), ("about", ABOUT % len(feats)),
                                   ("made_by", "E. Taciroglu (tools/build_csmip_buildings.py, ShakeReady)"), ("attributes", ATTRIBUTES)])
    head = json.dumps(out, ensure_ascii=False, indent=1)[:-2]                      # one building per line, so changes can be read
    body = ",\n".join(json.dumps(f, ensure_ascii=False) for f in feats)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(head + ',\n "features": [\n' + body + "\n ]\n}\n")
    json.load(open(OUT, encoding="utf-8"))                                           # the file reads back as JSON

    P = [f["properties"] for f in feats]
    count = lambda cond: sum(1 for p in P if cond(p))
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(feats)} buildings ({len(general)} + {len(nonductile)}), {len(set(p['station_number'] for p in P))} distinct station numbers")
    print(f"no station is in both files; the nearest pair across the two files is {facts['nearest_km']:.1f} km apart")
    print(f"values brought in line with the 55 ({len(changes)}):")
    for name, k, a, b in changes:
        print(f"   {name}: {k} {a!r} -> {b!r}")
    print("read from the text:")
    print(f"   stories             {count(lambda p: p['stories'] is not None)} of {len(P)}; not a plain number: " + "; ".join(f"{p['name']} ({p['Num of Stories']!r} -> {p['stories']})" for p in P if p['Num of Stories'] is not None and str(p['stories']) != p['Num of Stories']))
    print(f"   design_year         {count(lambda p: p['design_year'] is not None)} of {len(P)}; more than a year in the text: " + "; ".join(f"{p['name']} ({p['Design Date']!r} -> {p['design_year']})" for p in P if p['Design Date'] is not None and str(p['design_year']) != p['Design Date']))
    print(f"   instrumented_year   {count(lambda p: p['instrumented_year'] is not None)} of {len(P)}; none: " + "; ".join(f"{p['name']} ({p['Instrumentation']!r})" for p in P if p['instrumented_year'] is None))
    print(f"   accelerometers      {count(lambda p: p['accelerometers'] is not None)} of {len(P)}, from {min(p['accelerometers'] for p in P if p['accelerometers'])} to {max(p['accelerometers'] for p in P if p['accelerometers'])}")
    print(f"   instrumented_levels {count(lambda p: p['instrumented_levels'] is not None)} of {len(P)}, from {min(p['instrumented_levels'] for p in P if p['instrumented_levels'])} to {max(p['instrumented_levels'] for p in P if p['instrumented_levels'])}")
    print(f"   free_field          with {count(lambda p: p['free_field'] is True)}, without {count(lambda p: p['free_field'] is False)}, no text {count(lambda p: p['free_field'] is None)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
