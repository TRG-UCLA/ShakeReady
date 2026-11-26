"""Attach the HAZUS fragility classes of Los Angeles's non-ductile concrete buildings to the LA Times inventory.

The class assignments are by A. Nigdelioglu, Z. Tuna Deger and E. Taciroglu (data/sources/LA_HAZUS_Fragility_Mapping.xlsx).
This script pairs each row of that workbook with a building of the inventory, checks the pairing field by field,
and writes:

    data/latimes_concrete_buildings.geojson     each building gains its fragility class (other fields untouched)
    data/la_ndrcb_hazus_fragility.csv           the assignments as a table, with both numberings and coordinates
    data/fragility/hazus_ndrcb_la_classes.json  the twelve classes and how many buildings fall in each

Run from the repository root:  python tools/apply_ndrcb_fragility.py     (needs openpyxl)
Part of ShakeReady. Made by E. Taciroglu.
"""
import collections
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKBOOK = os.path.join(ROOT, "data", "sources", "LA_HAZUS_Fragility_Mapping.xlsx")
GEOJSON = os.path.join(ROOT, "data", "latimes_concrete_buildings.geojson")
AUTHORS = ["A. Nigdelioglu", "Z. Tuna Deger", "E. Taciroglu"]
ADDED = ("fragility_mapping_id", "hazus_fragility_class", "hazus_fragility_description", "hazus_fragility_table")


def num(v):
    return None if v in (None, "") else int(float(v))


def main():
    import openpyxl
    wb = openpyxl.load_workbook(WORKBOOK, data_only=True)
    rows = list(wb["Building Mapping"].iter_rows(values_only=True))
    head = rows[0]
    mapping = [dict(zip(head, r)) for r in rows[1:] if r[0] is not None]
    classes = {}
    for r in wb["Class Summary"].iter_rows(values_only=True):
        if r[0] and r[4] and str(r[4]).startswith("Table"):
            classes[r[0]] = {"class": r[0], "structural_system": r[1], "story_range": str(r[2]).replace("\u2013", "-"), "design_level": r[3],
                             "hazus_table": f"Hazus 6.1 {r[4]}", "buildings_in_workbook": int(r[5])}
    with open(GEOJSON, encoding="utf-8") as f:
        g = json.load(f)
    feats = g["features"]
    if [num(f["properties"]["num"]) for f in feats] != sorted(num(f["properties"]["num"]) for f in feats):
        sys.exit("The inventory is not in the order of its own numbering; the pairing below depends on that order.")
    if len(mapping) != len(feats):
        sys.exit(f"The workbook has {len(mapping)} buildings and the inventory {len(feats)}.")
    # The workbook numbers its rows 1 to 1,451. The inventory's own numbers skip three values, so the two numberings
    # differ. Row k of the workbook is the k-th building of the inventory, and that is checked here for every row.
    problems = []
    for m, f in zip(mapping, feats):
        p = f["properties"]
        same = (m["HAZUS Building Type"] == p["hazus"], m["Code Level"] == p["level"], num(m["Stories"]) == num(p["stories"]),
                num(m["Year Built"]) == num(p["yrblt"]), (m["Address"] or "").strip().upper() == (p["address"] or "").strip().upper(),
                m["HAZUS Fragility Class"] == f"{p['hazus']}-{p['level']}", m["HAZUS Fragility Class"] in classes)
        if not all(same):
            problems.append((m["Building ID"], p["num"], same))
    if problems:
        sys.exit(f"{len(problems)} rows of the workbook do not match the building they are paired with, for example {problems[:3]}. Nothing was written.")
    out_rows, counts = [], collections.Counter()
    for m, f in zip(mapping, feats):
        p, c = f["properties"], classes[m["HAZUS Fragility Class"]]
        for key in ADDED:
            p.pop(key, None)
        p["fragility_mapping_id"] = int(m["Building ID"])
        p["hazus_fragility_class"] = c["class"]
        p["hazus_fragility_description"] = f"{c['structural_system']}, {c['story_range']} stories, {c['design_level']}"
        p["hazus_fragility_table"] = c["hazus_table"]
        counts[c["class"]] += 1
        lon, lat = f["geometry"]["coordinates"][:2]
        out_rows.append([int(m["Building ID"]), num(p["num"]), c["class"], m["HAZUS Building Type"], m["Code Level"], m["Seismic Design Level"], c["structural_system"], c["story_range"],
                         c["hazus_table"], num(m["Stories"]), num(m["Year Built"]) if m["Year Built"] not in (None, "") else "", m["Address"], m["Occupancy"], lat, lon,
                         "demolished, per the source's update note" if "demolished" in (p.get("Update") or "") else ""])
    for name, c in classes.items():
        if counts[name] != c["buildings_in_workbook"]:
            sys.exit(f"Class {name}: {counts[name]} buildings counted here, {c['buildings_in_workbook']} in the workbook's summary.")
    with open(GEOJSON, "w", encoding="utf-8") as f:
        json.dump(g, f, ensure_ascii=False)
    with open(os.path.join(ROOT, "data", "la_ndrcb_hazus_fragility.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["mapping_building_id", "inventory_num", "hazus_fragility_class", "hazus_building_type", "code_level", "seismic_design_level", "structural_system", "story_range",
                    "hazus_table", "stories", "year_built", "address", "occupancy", "latitude", "longitude", "note"])
        w.writerows(out_rows)
    summary = {"title": "HAZUS fragility classes of Los Angeles's non-ductile reinforced concrete buildings", "developed_by": AUTHORS,
               "applies_to": "latimes-concrete", "buildings": len(out_rows),
               "reference": "FEMA Hazus 6.1 Earthquake Model Technical Manual (July 2024): Table 5-1 for building types; Tables 5-21 (Low-Code) and 5-22 (Pre-Code) for structural fragility, as cited in the workbook",
               "what_this_holds": "Which fragility class each building belongs to. The curves' parameters are in the manual's tables and are not reproduced here.",
               "classes": [dict(classes[k], buildings=counts[k]) for k in classes],
               "numbering": "mapping_building_id is the workbook's row number, 1 to 1,451. inventory_num is the LA Times inventory's own number, which skips 486, 820 and 983 and so runs to 1,454.",
               "notes": ["The design level recorded in the source inventory is used for every building, including the 214 with no construction year.",
                         "Four buildings are recorded as demolished in the source's update notes (workbook rows 870 to 873, inventory numbers 872 to 875). They remain in the table, marked."]}
    with open(os.path.join(ROOT, "data", "fragility", "hazus_ndrcb_la_classes.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    demolished = sum(1 for r in out_rows if r[-1])
    print(f"paired and checked {len(out_rows)} buildings; {len(classes)} classes; {demolished} marked demolished; classes:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
