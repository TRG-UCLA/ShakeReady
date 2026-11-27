#!/usr/bin/env python3
"""Reference for the shaking values the dashboard offers for every inventory.

Part of ShakeReady. Made by E. Taciroglu.

    python3 tools/shaking_reference.py <inventory id> hazards/<layer>.json [level id]      (from the repository root)

For each item of the inventory, in the order of its file: its identifier, its position, and each measure of the
hazard layer at that position. The values are read with SR-HazardMaker's own Python reader (bilinear interpolation of
the grid; a node without a value is left out), and rounded as the damage table is. This was written apart from the
dashboard, whose "Shaking values" downloads must give the same numbers: tools/tests/test_dashboard.py compares them.
A value is blank where the item lies outside the hazard layer.

The identifier is the structure number for the bridges, and for any other inventory the item's position in its file,
counting from 1.
"""
import csv
import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'vendor'))
from sr_hazardmaker import grid as hazard_grid      # SR-HazardMaker's own package, copied in by tools/sync_hazardmaker.py
from damage_reference import fmt                    # four decimals, an exact half rounded up (decision DMG-08)

ORDER = ('PGA', 'SA0P3', 'SA1P0')
COLUMN = {'PGA': 'pga_g', 'SA0P3': 'sa03_g', 'SA1P0': 'sa10_g'}


def deg(v):
    return str(Decimal(v).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP))


def table(inventory_id, hazard_path, level_id=None, registry_path='data/registry.json'):
    with open(registry_path, encoding='utf-8') as f:
        inv = next(i for i in json.load(f)['inventories'] if i['id'] == inventory_id)
    h = hazard_grid.load(hazard_path)
    hazard_grid.validate(h)
    level = next((lv for lv in h['levels'] if lv['id'] == (level_id or h.get('default_level'))), h['levels'][0])
    measures = [m for m in ORDER if m in level['measures']] + [m for m in level['measures'] if m not in ORDER]
    with open(inv['file'], encoding='utf-8') as f:
        data = json.load(f)
    if inv['format'] == 'nbi-rows':
        F = {name: i for i, name in enumerate(data['fields'])}
        items = [(r[F['structure_num']], r[F['lat']], r[F['lng']]) for r in data['rows']]
        first = 'structure_number'
    else:
        feats = [f for f in data['features'] if f.get('geometry')]
        items = [(i + 1, f['geometry']['coordinates'][1], f['geometry']['coordinates'][0]) for i, f in enumerate(feats)]
        first = 'item'
    columns = [first, 'latitude', 'longitude'] + [COLUMN.get(m, m.lower() + '_g') for m in measures]
    rows = [[str(ident), deg(lat), deg(lon)] + [fmt(hazard_grid.value_at(h, level['measures'][m], lat, lon)) for m in measures]
            for ident, lat, lon in items]
    return columns, rows


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    columns, rows = table(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    w = csv.writer(sys.stdout, lineterminator='\n')
    w.writerow(columns)
    w.writerows(rows)
