# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, E. Taciroglu. Part of SR-HazardMaker; see LICENSE.
"""Command line for SR-HazardMaker.

    sr-hazardmaker nshm ARCHIVE.zip                      a USGS hazard-model archive, or its map.csv tables
    sr-hazardmaker shakemap grid.xml                     a USGS ShakeMap grid, zipped or not
    sr-hazardmaker table points.csv --sa10 "SA(1.0)" --units g --title ... --site ... --source-title ... --publisher ...
    sr-hazardmaker scenario --magnitude 7 --mechanism strike-slip --from 34.40,-118.80 --to 34.10,-118.30 --publisher "Your name"
    sr-hazardmaker check layer.json                      check a layer and print its summary
    sr-hazardmaker cite                                  how to cite SR-HazardMaker

Each conversion writes <id>.json (the layer) and <id>.index-entry.json (its entry for a hazard
repository's index) to the output folder, and prints the checks and the checksum.
"""
import argparse
import datetime
import json
import os
import re
import sys
import unicodedata

from . import __author__, __version__, citation, grid, nshm, scenario, shakemap, table


def slug(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", s)[:60])


def _meta(args, base):
    """Merge what the file told us with what was given on the command line, and insist on a source."""
    src = dict(base.get("source") or {})
    for key, val in (("title", args.source_title), ("publisher", args.publisher), ("version", args.version),
                     ("doi", args.doi), ("url", args.url), ("contact", args.contact)):
        if val:
            src[key] = val
    if src.get("doi"):
        src["doi"] = re.sub(r"^https?://(dx\.)?doi\.org/", "", src["doi"], flags=re.I)
    src["retrieved_utc"] = args.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    meta = {"title": args.title or base.get("title", ""), "site_condition": args.site or base.get("site_condition", ""),
            "description": args.notes if args.notes is not None else base.get("description", ""),
            "default_level": args.default_level, "source": {k: v for k, v in src.items() if v}}
    meta["id"] = args.id or base.get("id") or slug(meta["title"])
    missing = [label for label, ok in (("a title (--title)", meta["title"]), ("an identifier (--id)", meta["id"]),
                                       ("the ground condition (--site)", meta["site_condition"]),
                                       ("the source's title (--source-title)", meta["source"].get("title")),
                                       ("the source's publisher or author (--publisher)", meta["source"].get("publisher"))) if not ok]
    if missing:
        raise ValueError("A layer must say where it comes from. Please give " + ", ".join(missing) + ".")
    return meta


def report(layer, out=sys.stdout):
    g = layer["grid"]
    lat_max = g["lat_min"] + (g["nlat"] - 1) * g["dlat"]
    lon_max = g["lon_min"] + (g["nlon"] - 1) * g["dlon"]
    print(f'{layer["id"]}: {layer["title"]}', file=out)
    print(f'  {"hazard map" if layer["kind"] == "probabilistic" else "one earthquake"} | ground condition: {layer["site_condition"]}', file=out)
    print(f'  grid {g["nlat"]} x {g["nlon"]} points, spacing {g["dlat"]} x {g["dlon"]} degrees, '
          f'{g["lat_min"]:.3f} to {lat_max:.3f} north, {g["lon_min"]:.3f} to {lon_max:.3f} east', file=out)
    for r in grid.summary(layer):
        rng = f'{r["min"]:.3f} to {r["max"]:.3f} g' if r["count"] else "no values"
        print(f'  {r["level"]:<8} {grid.MEASURE_NAMES[r["measure"]]:<10} {rng}, {r["count"]:,} of {r["total"]:,} points', file=out)
    errors, warnings = grid.check(layer)
    for w in warnings:
        print("  note:", w, file=out)
    for e in errors:
        print("  PROBLEM:", e, file=out)
    return errors


def write(layer, out_dir):
    errors = report(layer)
    if errors:
        print("The layer was not written.")
        return 1
    text = grid.serialize(layer)
    sha, nbytes = grid.sha256_text(text), len(text.encode("utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, layer["id"] + ".json")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    with open(os.path.join(out_dir, layer["id"] + ".index-entry.json"), "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(grid.index_entry(layer, sha, nbytes), indent=1, ensure_ascii=False) + "\n")
    print(f"  wrote {path} ({nbytes / 1e6:.2f} MB) and its index entry")
    print(f"  sha256 {sha}")
    print("  Made with SR-HazardMaker. If you use this layer in your work, please cite the tool: sr-hazardmaker cite")
    return 0


def cmd_nshm(a):
    groups, notes = nshm.find(a.files)
    for n in notes:
        print(n)
    usable = [g for g in groups if "SA1P0" in groups[g]]
    if not usable:
        raise ValueError("No Sa(1.0 s) hazard-map table (SA1P0) was found in what you gave.")
    label = a.site_condition or usable[0]
    if label not in groups:
        raise ValueError(f'No tables for "{label}". Found: {", ".join(usable)}.')
    if len(usable) > 1 and not a.site_condition:
        print(f'Several site conditions found ({", ".join(usable)}); using "{label}". Choose another with --site-condition.')
    items = groups[label]
    base = nshm.defaults(label, list(a.files) + [it["name"] for it in items.values()])
    return write(nshm.build(items, _meta(a, base), generator=f"SR-HazardMaker {__version__}, command line (USGS hazard-model files)"), a.out)


def cmd_shakemap(a):
    text, name = shakemap.read_text(a.file)
    p = shakemap.parse(text, name)
    filled = sum(v != grid.NODATA for v in p["measures"]["SA1P0"])
    print(f'{name}: {p["rows"]:,} rows read; {filled:,} of {p["expected"]:,} grid points filled'
          + (f'; {p["off"]:,} rows fell outside the stated grid' if p["off"] else ""))
    return write(shakemap.build(p, _meta(a, shakemap.defaults(p)), name, generator=f"SR-HazardMaker {__version__}, command line (USGS ShakeMap grid)"), a.out)


def cmd_table(a):
    with open(a.file, encoding="utf-8-sig", newline="") as f:
        t = table.read(f.read())
    mapping = {}
    for key, given in (("lon", a.lon), ("lat", a.lat), ("SA1P0", a.sa10), ("SA0P3", a.sa03), ("PGA", a.pga)):
        mapping[key] = table.column(t, given) if given else t["guess"][key] if key in ("lon", "lat", "SA1P0") else -1
    print("columns used:", {k: t["header"][i] for k, i in mapping.items() if i >= 0})
    meta = _meta(a, {})
    meta.update(kind=a.kind, level_label=a.level_label, file_name=os.path.basename(a.file))
    return write(table.build(t, mapping, a.units, meta, generator=f"SR-HazardMaker {__version__}, command line (table of points)"), a.out)


def _point(text, flag):
    try:
        return scenario.parse_point(text)
    except ValueError:
        raise ValueError(f'{flag} needs a latitude and a longitude, for example {flag} 34.40,-118.80 (west longitudes are negative)')


def cmd_scenario(a):
    p = {"magnitude": a.magnitude, "mechanism": a.mechanism, "trace": [_point(a.start, "--from"), _point(a.end, "--to")],
         "dip": a.dip, "width_km": a.width, "vs30": a.vs30, "epsilon": a.epsilon, "spacing": a.spacing, "margin_km": a.margin_km}
    base = scenario.defaults(p)
    print("Ground-motion model:", scenario.bssa14.CITATION)
    return write(scenario.build(p, _meta(a, base), generator=f"SR-HazardMaker {__version__}, command line (scenario builder)"), a.out)


def cmd_check(a):
    layer = grid.load(a.file)
    errors = report(layer)
    with open(a.file, "rb") as f:
        import hashlib
        print("  sha256", hashlib.sha256(f.read()).hexdigest())
    print("OK" if not errors else "NOT USABLE")
    return 1 if errors else 0


def cmd_cite(a):
    c = citation()
    print("If you use SR-HazardMaker, please cite it:\n")
    print(c["text"] + "\n")
    print(c["bibtex"])
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="sr-hazardmaker", description="Turn ground-motion data into hazard layers for the ShakeReady map.")
    p.add_argument("--version", action="version", version=f"SR-HazardMaker {__version__}, made by {__author__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp):
        sp.add_argument("--out", default=".", help="folder to write to (default: here)")
        sp.add_argument("--id", help="identifier; becomes the file name")
        sp.add_argument("--title")
        sp.add_argument("--site", help="the ground condition the values assume, in words")
        sp.add_argument("--notes", help="how the ground motions were produced")
        sp.add_argument("--source-title"); sp.add_argument("--publisher", help="publisher or author of the source")
        sp.add_argument("--version", help="version of the source"); sp.add_argument("--doi"); sp.add_argument("--url")
        sp.add_argument("--date", help="date obtained or made, YYYY-MM-DD (default: today)")
        sp.add_argument("--contact"); sp.add_argument("--default-level", help="level the map selects first, e.g. rp975")

    s = sub.add_parser("nshm", help="USGS National Seismic Hazard Model archive or map.csv tables")
    s.add_argument("files", nargs="+"); s.add_argument("--site-condition", help='which site condition in the archive, e.g. "Vs30 = 760 m/s"')
    common(s); s.set_defaults(func=cmd_nshm)
    s = sub.add_parser("shakemap", help="USGS ShakeMap grid.xml, zipped or not")
    s.add_argument("file"); common(s); s.set_defaults(func=cmd_shakemap)
    s = sub.add_parser("table", help="a CSV of points on a regular grid")
    s.add_argument("file")
    for flag, text in (("--lon", "longitude"), ("--lat", "latitude"), ("--sa10", "Sa(1.0 s)"), ("--sa03", "Sa(0.3 s)"), ("--pga", "PGA")):
        s.add_argument(flag, help=f"column holding {text}: its name or its number")
    s.add_argument("--units", default="g", help='units of the ground motions: g, %%g, cm/s2 or m/s2 (default g)')
    s.add_argument("--kind", choices=("scenario", "probabilistic"), default="scenario")
    s.add_argument("--level-label", help="name of the level, for a hazard map")
    common(s); s.set_defaults(func=cmd_table)
    s = sub.add_parser("scenario", help="compute the shaking of a described earthquake with a ground-motion model")
    s.add_argument("--magnitude", type=float, required=True)
    s.add_argument("--mechanism", choices=tuple(scenario.bssa14.MECHANISMS), required=True, help="style of faulting")
    s.add_argument("--from", dest="start", required=True, metavar="LAT,LON", help="one end of the fault trace")
    s.add_argument("--to", dest="end", required=True, metavar="LAT,LON", help="the other end; a dipping fault dips to the right of the direction from --from to --to")
    s.add_argument("--dip", type=float, help="degrees from horizontal (default 90, vertical)")
    s.add_argument("--width", type=float, help="down-dip width of the rupture in km, for a dipping fault (default 15)")
    s.add_argument("--vs30", type=float, help="Vs30 used everywhere, m/s (default 760)")
    s.add_argument("--epsilon", type=float, help="standard deviations above the median (default 0, the median)")
    s.add_argument("--spacing", type=float, help="grid spacing in degrees (default 0.02)")
    s.add_argument("--margin-km", type=float, help="how far the grid extends beyond the fault (default 100)")
    common(s); s.set_defaults(func=cmd_scenario)
    s = sub.add_parser("check", help="check a layer file and print its summary")
    s.add_argument("file"); s.set_defaults(func=cmd_check)
    s = sub.add_parser("cite", help="how to cite SR-HazardMaker")
    s.set_defaults(func=cmd_cite)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except (ValueError, OSError) as err:
        print("Error:", err, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
