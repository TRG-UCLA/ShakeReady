#!/usr/bin/env python3
"""Convert USGS National Seismic Hazard Model uniform-hazard map files into a ShakeReady hazard grid.

Input: the `map.csv` files of a USGS NSHM data release for one site condition, one per intensity
measure. Each has a longitude column, a latitude column, and one column of ground motion (in g) per
return period, for example 475, 975 and 2475 years.

Usage:
    python3 tools/build_hazard_nshm.py --id nshm-2023r2-bc --title "USGS National Seismic Hazard Model 2023 (revision 2)" \\
        --site "Reference site condition, Vs30 = 760 m/s (site class BC)" \\
        --sa10 SA1P0_map.csv --sa03 SA0P3_map.csv --pga PGA_map.csv \\
        --source-json source.json

The output is cropped to a box around California and written to hazards/<id>.json. The layer is
then listed in hazards/index.json.
"""
import argparse, csv, datetime, hashlib, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hazard_grid

BOUNDS = dict(lat_min=32.0, lat_max=42.5, lon_min=-125.0, lon_max=-113.5)   # California with a margin
SCALE = 0.001          # stored in thousandths of g
NODATA = -1
LEVEL_INFO = {         # return period (years): probability statement
    475: '10% probability of exceedance in 50 years',
    975: '5% probability of exceedance in 50 years',
    2475: '2% probability of exceedance in 50 years',
    10000: '1% probability of exceedance in 100 years',
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_map_csv(path):
    """Return {return_period: {(lat, lon): value}} for the nodes inside BOUNDS, and the column names."""
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = csv.reader(f)
        header = [c.strip() for c in next(rows)]
        low = [c.lower() for c in header]
        try:
            ilon = next(i for i, c in enumerate(low) if c in ('lon', 'longitude', 'long', 'x'))
            ilat = next(i for i, c in enumerate(low) if c in ('lat', 'latitude', 'y'))
        except StopIteration:
            sys.exit(f"{path}: no longitude/latitude columns found in header {header}")
        periods = {}
        for i, c in enumerate(header):
            try:
                rp = float(c)
            except ValueError:
                continue
            if rp >= 50:                       # a return period in years, not a coordinate
                periods[int(round(rp))] = i
        if not periods:
            sys.exit(f"{path}: no return-period columns found in header {header}")
        out = {rp: {} for rp in periods}
        for r in rows:
            if not r:
                continue
            lon, lat = float(r[ilon]), float(r[ilat])
            if not (BOUNDS['lat_min'] <= lat <= BOUNDS['lat_max'] and BOUNDS['lon_min'] <= lon <= BOUNDS['lon_max']):
                continue
            key = (round(lat, 4), round(lon, 4))
            for rp, i in periods.items():
                cell = r[i].strip() if i < len(r) else ''
                if cell not in ('', 'NaN', 'nan', 'null'):
                    out[rp][key] = float(cell)
    return out, header


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--id', required=True); ap.add_argument('--title', required=True)
    ap.add_argument('--site', required=True, help='site condition, in words')
    ap.add_argument('--sa10', required=True); ap.add_argument('--sa03'); ap.add_argument('--pga')
    ap.add_argument('--description', default='')
    ap.add_argument('--source-json', help='JSON file with the source record: title, publisher, url, doi, version, retrieved_utc, note')
    ap.add_argument('--default-level', type=int, help='return period, in years, that the map selects first')
    ap.add_argument('--out-dir', default='hazards')
    a = ap.parse_args()

    files = {'SA1P0': a.sa10, 'SA0P3': a.sa03, 'PGA': a.pga}
    data = {m: read_map_csv(p)[0] for m, p in files.items() if p}
    periods = sorted(set.intersection(*(set(d) for d in data.values())))
    if not periods:
        sys.exit('the files share no return period')

    nodes = set()
    for d in data.values():
        for rp in periods:
            nodes.update(d[rp])
    lats = sorted({k[0] for k in nodes}); lons = sorted({k[1] for k in nodes})
    dlat = round(min(b - a_ for a_, b in zip(lats, lats[1:])), 4)
    dlon = round(min(b - a_ for a_, b in zip(lons, lons[1:])), 4)
    nlat = int(round((lats[-1] - lats[0]) / dlat)) + 1
    nlon = int(round((lons[-1] - lons[0]) / dlon)) + 1
    if any(abs((la - lats[0]) / dlat - round((la - lats[0]) / dlat)) > 1e-3 for la in lats) or \
       any(abs((lo - lons[0]) / dlon - round((lo - lons[0]) / dlon)) > 1e-3 for lo in lons):
        sys.exit('the nodes do not lie on a regular grid')

    levels = []
    for rp in periods:
        measures = {}
        for m, d in data.items():
            arr = [NODATA] * (nlat * nlon)
            for (la, lo), v in d[rp].items():
                j = int(round((la - lats[0]) / dlat)); i = int(round((lo - lons[0]) / dlon))
                arr[j * nlon + i] = int(math.floor(v / SCALE + 0.5))      # a half rounds up, as in HazardMaker
            measures[m] = arr
        levels.append({'id': f'rp{rp}', 'label': f'{rp:,}-year return period' + (f' ({LEVEL_INFO[rp]})' if rp in LEVEL_INFO else ''),
                       'return_period_years': rp, 'measures': measures})

    source = json.load(open(a.source_json, encoding='utf-8')) if a.source_json else {}
    source['input_files'] = [{'measure': m, 'file': os.path.basename(p), 'sha256': sha256(p), 'bytes': os.path.getsize(p)} for m, p in files.items() if p]
    hazard = {
        'format': hazard_grid.FORMAT, 'id': a.id, 'title': a.title, 'kind': 'probabilistic',
        'description': a.description, 'site_condition': a.site, 'units': 'g', 'scale': SCALE, 'nodata': NODATA,
        'grid': {'lat_min': lats[0], 'lon_min': lons[0], 'dlat': dlat, 'dlon': dlon, 'nlat': nlat, 'nlon': nlon},
        'default_level': f'rp{a.default_level}' if a.default_level else levels[0]['id'],
        'levels': levels, 'source': source,
        'provenance': {'generator': 'tools/build_hazard_nshm.py',
                       'generated_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                       'cropped_to': BOUNDS, 'stored_precision_g': SCALE},
    }
    hazard_grid.validate(hazard)
    os.makedirs(a.out_dir, exist_ok=True)
    out = os.path.join(a.out_dir, a.id + '.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(hazard, f, separators=(',', ':'), ensure_ascii=False)

    index_path = os.path.join(a.out_dir, 'index.json')
    index = json.load(open(index_path, encoding='utf-8')) if os.path.exists(index_path) else {'hazards': []}
    entry = {'id': a.id, 'title': a.title, 'kind': 'probabilistic', 'file': f'{a.out_dir}/{a.id}.json'.replace(os.sep, '/'),
             'site_condition': a.site, 'description': a.description, 'measures': sorted(data),
             'levels': [{'id': lv['id'], 'label': lv['label']} for lv in levels],
             'source': {k: source.get(k) for k in ('title', 'publisher', 'url', 'doi', 'version', 'retrieved_utc') if source.get(k)},
             'sha256': sha256(out), 'bytes': os.path.getsize(out), 'default': True}
    index['hazards'] = [h for h in index['hazards'] if h['id'] != a.id]
    if entry['default']:
        for h in index['hazards']:
            h.pop('default', None)
    index['hazards'].insert(0, entry)
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=1, ensure_ascii=False)
    filled = sum(v != NODATA for v in levels[0]['measures']['SA1P0'])
    print(f"wrote {out}: {nlat} x {nlon} nodes at {dlat} x {dlon} degrees, {filled:,} with values, "
          f"levels {[lv['id'] for lv in levels]}, measures {sorted(data)}, {os.path.getsize(out) / 1e6:.2f} MB")


if __name__ == '__main__':
    main()
