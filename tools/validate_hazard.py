#!/usr/bin/env python3
"""Check a hazard grid file before it is added to hazards/index.json, and print a summary.

Usage:
    python3 tools/validate_hazard.py hazards/<file>.json
"""
import hashlib, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hazard_grid

CALIFORNIA = dict(lat_min=32.5, lat_max=42.0, lon_min=-124.5, lon_max=-114.1)


def main(path):
    h = hazard_grid.load(path)
    hazard_grid.validate(h)
    g = h['grid']
    lat_max = g['lat_min'] + (g['nlat'] - 1) * g['dlat']
    lon_max = g['lon_min'] + (g['nlon'] - 1) * g['dlon']
    problems = []
    if lat_max < CALIFORNIA['lat_min'] or g['lat_min'] > CALIFORNIA['lat_max'] or lon_max < CALIFORNIA['lon_min'] or g['lon_min'] > CALIFORNIA['lon_max']:
        problems.append('the grid does not overlap California')
    src = h.get('source') or {}
    for key in ('title', 'publisher', 'retrieved_utc'):
        if not src.get(key):
            problems.append(f"source.{key} is missing; a layer needs to say where it came from")
    print(f"{h['id']}: {h['title']}")
    print(f"  kind: {h['kind']} | site condition: {h['site_condition']}")
    print(f"  grid: {g['nlat']} x {g['nlon']} nodes, {g['dlat']} x {g['dlon']} degrees, "
          f"latitude {g['lat_min']} to {lat_max:.4f}, longitude {g['lon_min']} to {lon_max:.4f}")
    for lv in h['levels']:
        for m, arr in lv['measures'].items():
            vals = [v * h['scale'] for v in arr if v != h['nodata']]
            if not vals:
                problems.append(f"level {lv['id']}, {m}: no values at all"); continue
            if min(vals) < 0 or max(vals) > 10:
                problems.append(f"level {lv['id']}, {m}: values outside 0 to 10 g ({min(vals):.3f} to {max(vals):.3f}); check the units")
            print(f"  level {lv['id']:<8} {m:<6} {min(vals):.3f} to {max(vals):.3f} g, {100 * (1 - len(vals) / len(arr)):.1f}% of nodes without a value")
    with open(path, 'rb') as f:
        print(f"  sha256: {hashlib.sha256(f.read()).hexdigest()} | {os.path.getsize(path):,} bytes")
    if problems:
        print('PROBLEMS:'); [print('  -', p) for p in problems]
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
