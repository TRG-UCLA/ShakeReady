#!/usr/bin/env python3
"""Reference calculation of bridge damage: the same table the map offers for download.

For every bridge in data/bridges.json, read the ground motion at its location from a hazard file,
apply the HAZUS highway bridge fragilities, and write the asset-by-asset table. This is an
independent implementation in Python, used to check the map's own calculation and to let anyone
reproduce a downloaded table.

Usage:
    python3 tools/damage_reference.py hazards/<id>.json [level-id] > damage.csv
"""
import csv, json, os, sys
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor'))
from sr_hazardmaker import grid as hazard_grid      # SR-HazardMaker's own package, copied in by tools/sync_hazardmaker.py
import hazus_bridges as hz

COLUMNS = ['structure_number', 'latitude', 'longitude', 'county', 'year_built', 'hazus_class', 'design', 'main_spans', 'skew_deg',
           'sa10_g', 'sa03_g', 'k_skew', 'k_3d', 'factor_slight',
           'median_slight_g', 'median_moderate_g', 'median_extensive_g', 'median_complete_g',
           'p_none', 'p_slight', 'p_moderate', 'p_extensive', 'p_complete', 'p_extensive_or_complete', 'most_likely_state']
STATES = ['None', 'Slight', 'Moderate', 'Extensive', 'Complete']


def bridge_result(h, level, r, F):
    """One bridge's result as a dict keyed by COLUMNS (ground-motion and damage fields blank if no value)."""
    cls = r[F['hazus']]
    c = hz.CLASSES[cls]
    spans, skew = r[F['spans_main']], r[F['skew']]
    out = {'hazus_class': f'HWB{cls}', 'design': c['design'], 'main_spans': spans, 'skew_deg': skew,
           'k_skew': hz.k_skew(skew), 'k_3d': hz.k_3d(cls, spans)}
    m = level['measures']
    sa10 = hazard_grid.value_at(h, m['SA1P0'], r[F['lat']], r[F['lng']])
    sa03 = hazard_grid.value_at(h, m['SA0P3'], r[F['lat']], r[F['lng']]) if 'SA0P3' in m else None
    if sa10 is None:
        return out
    out['sa10_g'], out['sa03_g'] = sa10, sa03
    med = hz.adjusted_medians(cls, spans, skew, sa10, sa03)
    out['factor_slight'] = med[0] / c['medians'][0]
    for name, v in zip(('slight', 'moderate', 'extensive', 'complete'), med):
        out[f'median_{name}_g'] = v
    p = hz.damage_probabilities(cls, spans, skew, sa10, sa03)
    for name, v in zip(('none', 'slight', 'moderate', 'extensive', 'complete'), p):
        out[f'p_{name}'] = v
    out['p_extensive_or_complete'] = p[3] + p[4]
    best = max(range(5), key=lambda i: (p[i], -i))          # a tie goes to the milder state
    out['most_likely_state'] = STATES[best]
    return out


def fmt(v):
    """Four decimals, an exact half rounded up: the same rule as the map's own table."""
    if v is None or v == '':
        return ''
    if isinstance(v, float):
        return str(Decimal(v).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))
    return str(v)


def table(hazard_path, level_id=None, bridges_path='data/bridges.json'):
    h = hazard_grid.load(hazard_path)
    hazard_grid.validate(h)
    level = next((lv for lv in h['levels'] if lv['id'] == (level_id or h.get('default_level'))), h['levels'][0])
    d = json.load(open(bridges_path, encoding='utf-8'))
    F = {f: i for i, f in enumerate(d['fields'])}
    rows = []
    for r in d['rows']:
        res = bridge_result(h, level, r, F)
        deg = lambda v: str(Decimal(v).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP))
        res.update({'structure_number': r[F['structure_num']], 'latitude': deg(r[F['lat']]), 'longitude': deg(r[F['lng']]),
                    'county': d['counties'][r[F['county_i']]], 'year_built': r[F['year_built']]})
        rows.append([fmt(res.get(c)) for c in COLUMNS])
    return h, level, rows


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    h, level, rows = table(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    w = csv.writer(sys.stdout, lineterminator='\n')
    w.writerow(COLUMNS)
    w.writerows(rows)
