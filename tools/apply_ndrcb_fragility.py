"""Attach the HAZUS fragility classes of Los Angeles's non-ductile concrete buildings to the LA Times inventory.

The class assignments are by A. Nigdelioglu, Z. Tuna Deger and E. Taciroglu (data/sources/LA_HAZUS_Fragility_Mapping_Updated.xlsx).
This script joins each row of that workbook to a building of the inventory on the inventory's own number, checks the
join field by field, adds each class's curve parameters from the Hazus manual, and writes:

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
WORKBOOK = os.path.join(ROOT, "data", "sources", "LA_HAZUS_Fragility_Mapping_Updated.xlsx")
GEOJSON = os.path.join(ROOT, "data", "latimes_concrete_buildings.geojson")
AUTHORS = ["A. Nigdelioglu", "Z. Tuna Deger", "E. Taciroglu"]
ADDED = ("fragility_mapping_id", "hazus_fragility_class", "hazus_fragility_description", "hazus_fragility_table")
STATES = ("slight", "moderate", "extensive", "complete")
# FEMA Hazus 6.1 Earthquake Model Technical Manual (July 2024), Tables 5-21 (Low-Code, "LC") and 5-22 (Pre-Code, "PC"),
# "Structural Fragility Curve Parameters", for the concrete types of this inventory. For each type: roof height and modal
# height in inches; the inter-story drift ratio at the threshold of slight, moderate, extensive and complete damage; then,
# for the same four states in turn, the median spectral displacement in inches and its beta. Read from the manual's text
# by script and compared, row by row, with the authors' own extract of the two tables. In Table 5-21 the manual marks the
# C3 types with an asterisk: types not permitted by current seismic codes.
HAZUS_STRUCTURAL = {
    "LC": {"C2H": [1440.0, 864.0, 0.002, 0.0038, 0.0099, 0.025, 1.73, 0.68, 3.3, 0.73, 8.53, 0.84, 21.6, 0.95], "C2L": [240.0, 180.0, 0.004, 0.0076, 0.0197, 0.05, 0.72, 1.04, 1.37, 1.02, 3.55, 0.99, 9.0, 0.95], "C2M": [600.0, 450.0, 0.0027, 0.0051, 0.0132, 0.0333, 1.2, 0.83, 2.29, 0.81, 5.92, 0.82, 15.0, 1.0], "C3H": [1440.0, 864.0, 0.0015, 0.003, 0.0075, 0.0175, 1.3, 0.71, 2.59, 0.74, 6.48, 0.9, 15.12, 0.96], "C3L": [240.0, 180.0, 0.003, 0.006, 0.015, 0.035, 0.54, 1.09, 1.08, 1.07, 2.7, 1.08, 6.3, 0.91], "C3M": [600.0, 450.0, 0.002, 0.004, 0.01, 0.0233, 0.9, 0.85, 1.8, 0.83, 4.5, 0.79, 10.5, 0.98]},
    "PC": {"C2H": [1440.0, 864.0, 0.0016, 0.0031, 0.0079, 0.02, 1.38, 0.73, 2.64, 0.75, 6.82, 0.92, 17.28, 0.97], "C2L": [240.0, 180.0, 0.0032, 0.0061, 0.0158, 0.04, 0.58, 1.12, 1.1, 1.08, 2.84, 1.06, 7.2, 0.93], "C2M": [600.0, 450.0, 0.0021, 0.0041, 0.0105, 0.0267, 0.96, 0.86, 1.83, 0.83, 4.74, 0.8, 12.0, 0.98], "C3H": [1440.0, 864.0, 0.0012, 0.0024, 0.006, 0.014, 1.04, 0.73, 2.07, 0.74, 5.18, 0.9, 12.1, 0.95], "C3L": [240.0, 180.0, 0.0024, 0.0048, 0.012, 0.028, 0.43, 1.19, 0.86, 1.15, 2.16, 1.16, 5.04, 0.92], "C3M": [600.0, 450.0, 0.0016, 0.0032, 0.008, 0.0187, 0.72, 0.9, 1.44, 0.86, 3.6, 0.9, 8.4, 0.96]}
}


def num(v):
    return None if v in (None, "") else int(float(v))


def class_parameters(name):
    t, lv = name.split("-")
    v = HAZUS_STRUCTURAL[lv][t]
    out = {"roof_height_in": v[0], "modal_height_in": v[1], "drift_at_threshold": dict(zip(STATES, v[2:6])),
           "spectral_displacement_in": {s: {"median": v[6 + 2 * j], "beta": v[7 + 2 * j]} for j, s in enumerate(STATES)}}
    if lv == "LC" and t.startswith("C3"):
        out["manual_note"] = "Marked in Table 5-21 as a type not permitted by current seismic codes."
    return out


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
    # The workbook carries the inventory's own number beside its own row number. The join is on that number, and every
    # joined pair is checked field by field. (The first version of the workbook had only row numbers; pairing in order
    # then gave the same result as this join does.)
    by_num = {num(f["properties"]["num"]): f for f in feats}
    if sorted(m["Source num"] for m in mapping) != sorted(by_num):
        sys.exit("The workbook's source numbers are not the inventory's numbers.")
    feats = [by_num[m["Source num"]] for m in mapping]
    for lv, table in HAZUS_STRUCTURAL.items():          # the manual's own rule guards the transcription: median = drift x modal height
        for t, v in table.items():
            for j in range(4):
                if abs(v[6 + 2 * j] / (v[2 + j] * v[1]) - 1) > 0.02:
                    sys.exit(f"Curve parameters for {t}-{lv} are not consistent with the manual's own rule.")
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
        par = HAZUS_STRUCTURAL[m["Code Level"]][m["HAZUS Building Type"]]
        notes = ["demolished, per the source's update note"] if "demolished" in (p.get("Update") or "") else []
        if (m["Occupancy"] or "") != (p.get("name") or ""):
            notes.append("occupancy entered by the authors; blank in the source")
        out_rows.append([int(m["Building ID"]), num(p["num"]), c["class"], m["HAZUS Building Type"], m["Code Level"], m["Seismic Design Level"], c["structural_system"], c["story_range"],
                         c["hazus_table"], num(m["Stories"]), num(m["Year Built"]) if m["Year Built"] not in (None, "") else "", m["Address"], m["Occupancy"], lat, lon]
                        + par[2:6] + ["; ".join(notes)])
    for name, c in classes.items():
        if counts[name] != c["buildings_in_workbook"]:
            sys.exit(f"Class {name}: {counts[name]} buildings counted here, {c['buildings_in_workbook']} in the workbook's summary.")
    with open(GEOJSON, "w", encoding="utf-8") as f:
        json.dump(g, f, ensure_ascii=False)
    with open(os.path.join(ROOT, "data", "la_ndrcb_hazus_fragility.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["mapping_building_id", "inventory_num", "hazus_fragility_class", "hazus_building_type", "code_level", "seismic_design_level", "structural_system", "story_range",
                    "hazus_table", "stories", "year_built", "address", "occupancy", "latitude", "longitude",
                    "drift_at_slight", "drift_at_moderate", "drift_at_extensive", "drift_at_complete", "note"])
        w.writerows(out_rows)
    summary = {"title": "HAZUS fragility classes of Los Angeles's non-ductile reinforced concrete buildings", "developed_by": AUTHORS,
               "applies_to": "latimes-concrete", "buildings": len(out_rows),
               "reference": "FEMA Hazus 6.1 Earthquake Model Technical Manual (July 2024): Table 5-1 for building types; Tables 5-21 (Low-Code) and 5-22 (Pre-Code) for structural fragility, as cited in the workbook",
               "what_this_holds": "Which fragility class each building belongs to, and each class's structural fragility parameters from the manual: the inter-story drift ratio at the threshold of each damage state, and the median and beta of the spectral displacement curve for each state.",
               "units": {"heights": "inches", "drift": "ratio of inter-story drift to story height", "spectral_displacement": "inches", "beta": "lognormal standard deviation"},
               "classes": [dict(classes[k], buildings=counts[k], **class_parameters(k)) for k in classes],
               "numbering": "mapping_building_id is the workbook's row number, 1 to 1,451. inventory_num is the LA Times inventory's own number, which skips 486, 820 and 983 and so runs to 1,454.",
               "notes": ["The design level recorded in the source inventory is used for every building, including the 214 with no construction year.",
                         "Four buildings are recorded as demolished in the source's update notes (workbook rows 870 to 873, inventory numbers 872 to 875). They remain in the table, marked.",
                         "The occupancy of one building, 302 W 2nd St, is blank in the source; the authors looked it up and entered Office.",
                         "The parameters are the manual's, for the building type and design level; they are not specific to any one building."]}
    with open(os.path.join(ROOT, "data", "fragility", "hazus_ndrcb_la_classes.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    demolished = sum(1 for r in out_rows if "demolished" in r[-1])
    print(f"paired and checked {len(out_rows)} buildings; {len(classes)} classes; {demolished} marked demolished; classes:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
