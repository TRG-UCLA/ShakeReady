#!/usr/bin/env python3
"""Reference for the building damage table of the dashboard: every building of an inventory, by one of the two methods.

Part of ShakeReady. Made by E. Taciroglu.

    python3 tools/building_damage_reference.py <fragility id> hazards/<layer>.json [level id]      (from the repository root)

<fragility id> is an entry under "fragilities" in data/registry.json, such as hazus-buildings-capacity-spectrum or
hazus-buildings-equivalent-pga. The table has one row per building of the inventory that set applies to, in the order
of its file, with the same columns and rounding as the table the dashboard offers. The calculation is that of
tools/hazus_buildings.py; the ground motion at each building is read with SR-HazardMaker's own Python reader. It was
written apart from the dashboard, which must give the same rows: tools/tests/test_dashboard.py compares them.
"""
import csv
import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'vendor'))
from sr_hazardmaker import grid as hazard_grid
from damage_reference import fmt                    # four decimals, an exact half rounded up (decision DMG-08)
import hazus_buildings as hb

TAIL = ['p_none', 'p_slight', 'p_moderate', 'p_extensive', 'p_complete', 'p_slight_or_worse', 'p_moderate_or_worse', 'p_extensive_or_worse',
        'most_likely_state', 'state_with_50pct_chance_or_worse']
COLUMNS = {
    'hazus-capacity-spectrum': ['sa03_g', 'sa10_g', 'duration', 'kappa', 'elastic_damping_pct', 'sd_in', 'sa_at_sd_g', 'effective_damping_pct', 'period_s'],
    'hazus-equivalent-pga': ['pga_g', 'sa10_g', 'pga_over_sa1', 'median_slight_g', 'median_moderate_g', 'median_extensive_g', 'median_complete_g'],
}


def deg(v):
    return str(Decimal(v).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP))


def states(p):
    """The most likely state (a tie goes to the milder one) and the worst state reached with at least a 50% chance."""
    best = 0
    for i in range(1, 5):
        if p[i] > p[best]:
            best = i
    acc, s50 = 0.0, 0
    for i in range(4, 0, -1):
        acc += p[i]
        if acc >= 0.5:
            s50 = i
            break
    return hb.STATES[best], hb.STATES[s50]


def table(fragility_id, hazard_path, level_id=None, registry_path='data/registry.json'):
    with open(registry_path, encoding='utf-8') as f:
        reg = json.load(f)
    entry = next(x for x in reg['fragilities'] if x['id'] == fragility_id)
    method = entry['method']
    with open(entry['file'], encoding='utf-8') as f:
        fset = json.load(f)
    inv = next(i for i in reg['inventories'] if fragility_id in i.get('fragilities', []))
    with open(inv['file'], encoding='utf-8') as f:
        feats = [x for x in json.load(f)['features'] if x.get('geometry')]
    own = inv.get('table_fields', [])
    classes = hb.load_classes()
    h = hazard_grid.load(hazard_path)
    hazard_grid.validate(h)
    level = next((lv for lv in h['levels'] if lv['id'] == (level_id or h.get('default_level'))), h['levels'][0])
    when = hb.timing(h, level)
    at = lambda name, lat, lon: hazard_grid.value_at(h, level['measures'][name], lat, lon) if name in level['measures'] else None
    columns = ['item', 'latitude', 'longitude'] + own + [fset['class_field']] + COLUMNS[method] + TAIL
    rows = []
    for i, ft in enumerate(feats):
        lon, lat = ft['geometry']['coordinates'][:2]
        p = ft['properties']
        cls = p.get(fset['class_field'])
        head = [str(i + 1), deg(lat), deg(lon)] + ['' if p.get(k) is None else str(p[k]) for k in own] + ['' if cls is None else str(cls)]
        blank = head + [''] * (len(COLUMNS[method]) + len(TAIL))
        if cls not in classes:
            rows.append(blank)
            continue
        if method == 'hazus-capacity-spectrum':
            sas, sa1 = at('SA0P3', lat, lon), at('SA1P0', lat, lon)
            if sas is None or sa1 is None:
                rows.append(blank)
                continue
            r = hb.method1(cls, sas, sa1, classes=classes, when=when)
            mid = [fmt(sas), fmt(sa1), r['duration'], fmt(r['kappa']), fmt(r['b_elastic']), fmt(r['d']), fmt(r['a']), fmt(r['b_eff']), fmt(r['period'])]
        else:
            pga, sa1 = at('PGA', lat, lon), at('SA1P0', lat, lon)
            if pga is None or sa1 is None:
                rows.append(blank)
                continue
            r = hb.method2(cls, pga, sa1=sa1, classes=classes)
            mid = [fmt(pga), fmt(sa1), fmt(r['ratio'])] + [fmt(m) for m in r['medians']]
        ex = r['exceedance']
        rows.append(head + mid + [fmt(v) for v in r['p']] + [fmt(ex[0]), fmt(ex[1]), fmt(ex[2])] + list(states(r['p'])))
    return columns, rows, when


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    columns, rows, when = table(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    w = csv.writer(sys.stdout, lineterminator='\n')
    w.writerow(columns)
    w.writerows(rows)
