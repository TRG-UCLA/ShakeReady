#!/usr/bin/env python3
"""Build the ShakeReady bridge layer from an FHWA National Bridge Inventory state file.

Usage:
    python3 tools/build_bridges.py CA25.txt

Input:  the comma-delimited state file from https://www.fhwa.dot.gov/bridge/nbi/ascii.cfm
        (text qualifier is a single quote; one header row).
Output: data/bridges.json   compact row format read by map.html
        data/nbi_bridges.csv  the same records as a labeled table for download

Each bridge is also assigned its HAZUS highway bridge class (see hazus_bridges.py).

Bridge inventory builder, part of ShakeReady. Made by E. Taciroglu.

Only Python's standard library is used.
"""
import csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hazus_bridges

SOURCE_YEAR_RE = re.compile(r'(\d{2})\.txt$', re.I)

KINDS = {  # Item 43A / 44A: kind of material and/or design
    '1': 'Concrete', '2': 'Continuous Concrete', '3': 'Steel', '4': 'Continuous Steel',
    '5': 'Prestressed Concrete', '6': 'Continuous Prestressed Concrete', '7': 'Wood or Timber',
    '8': 'Masonry', '9': 'Aluminum, Wrought Iron or Cast Iron', '0': 'Other',
}
TYPES = {  # Item 43B / 44B: type of design and/or construction
    '00': 'Other', '01': 'Slab', '02': 'Stringer/Multi-beam or Girder', '03': 'Girder and Floorbeam System',
    '04': 'Tee Beam', '05': 'Box Beam or Girders, Multiple', '06': 'Box Beam or Girders, Single or Spread',
    '07': 'Frame', '08': 'Orthotropic', '09': 'Deck Truss', '10': 'Through Truss', '11': 'Deck Arch',
    '12': 'Through Arch', '13': 'Suspension', '14': 'Stayed Girder', '15': 'Movable, Lift',
    '16': 'Movable, Bascule', '17': 'Movable, Swing', '18': 'Tunnel', '19': 'Culvert',
    '20': 'Mixed Types', '21': 'Segmental Box Girder', '22': 'Channel Beam',
}
CONDITIONS = {'G': 'Good', 'F': 'Fair', 'P': 'Poor'}
CA_COUNTIES = {  # FIPS county codes for California (Item 3)
    '001': 'Alameda', '003': 'Alpine', '005': 'Amador', '007': 'Butte', '009': 'Calaveras', '011': 'Colusa',
    '013': 'Contra Costa', '015': 'Del Norte', '017': 'El Dorado', '019': 'Fresno', '021': 'Glenn',
    '023': 'Humboldt', '025': 'Imperial', '027': 'Inyo', '029': 'Kern', '031': 'Kings', '033': 'Lake',
    '035': 'Lassen', '037': 'Los Angeles', '039': 'Madera', '041': 'Marin', '043': 'Mariposa',
    '045': 'Mendocino', '047': 'Merced', '049': 'Modoc', '051': 'Mono', '053': 'Monterey', '055': 'Napa',
    '057': 'Nevada', '059': 'Orange', '061': 'Placer', '063': 'Plumas', '065': 'Riverside',
    '067': 'Sacramento', '069': 'San Benito', '071': 'San Bernardino', '073': 'San Diego',
    '075': 'San Francisco', '077': 'San Joaquin', '079': 'San Luis Obispo', '081': 'San Mateo',
    '083': 'Santa Barbara', '085': 'Santa Clara', '087': 'Santa Cruz', '089': 'Shasta', '091': 'Sierra',
    '093': 'Siskiyou', '095': 'Solano', '097': 'Sonoma', '099': 'Stanislaus', '101': 'Sutter',
    '103': 'Tehama', '105': 'Trinity', '107': 'Tulare', '109': 'Tuolumne', '111': 'Ventura',
    '113': 'Yolo', '115': 'Yuba',
}
# Generous bounding box for California; records outside it are treated as having no usable location.
BBOX = (32.0, 42.1, -124.6, -114.0)


def dms_to_deg(packed, deg_digits):
    """NBI packs coordinates as DDMMSSss (latitude) or DDDMMSSss (longitude)."""
    s = packed.strip()
    if not s.isdigit() or len(s) != deg_digits + 6:
        return None
    d, m, sec = int(s[:deg_digits]), int(s[deg_digits:deg_digits + 2]), int(s[deg_digits + 2:]) / 100.0
    if m >= 60 or sec >= 60:
        return None
    return d + m / 60.0 + sec / 3600.0


def to_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def rating(v):
    """Condition ratings are 0-9, or N when the component does not apply. -1 stands for N."""
    v = (v or '').strip()
    return int(v) if v.isdigit() else -1


def index(table, value):
    if value not in table:
        table.append(value)
    return table.index(value)


def main(path):
    with open(path, newline='', encoding='latin-1') as f:
        records = list(csv.DictReader(f, quotechar="'"))

    m = SOURCE_YEAR_RE.search(os.path.basename(path))
    source_year = 2000 + int(m.group(1)) if m else None

    kinds, types, counties = [], [], []
    rows, table, no_location = [], [], 0
    fields = ['lat', 'lng', 'structure_num', 'year_built', 'year_recon', 'lanes_on', 'lanes_und',
              'adt', 'adt_year', 'adt_future', 'adt_year_future', 'kind_i', 'type_i', 'appr_kind_i',
              'appr_type_i', 'max_span', 'spans_main', 'spans_appr', 'length', 'deck', 'superstructure',
              'substructure', 'channel', 'culvert', 'cond', 'county_i', 'feature', 'facility', 'skew', 'hazus']

    for r in records:
        if r['RECORD_TYPE_005A'].strip() != '1':      # keep the route carried on the structure
            continue
        lat = dms_to_deg(r['LAT_016'], 2)
        lng = dms_to_deg(r['LONG_017'], 3)
        lng = -lng if lng is not None else None      # NBI stores west longitude as a positive number
        located = (lat is not None and lng is not None
                   and BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lng <= BBOX[3])

        kind = KINDS.get(r['STRUCTURE_KIND_043A'].strip(), 'Other')
        typ = TYPES.get(r['STRUCTURE_TYPE_043B'].strip().zfill(2), 'Other')
        spans_appr = to_int(r['APPR_SPANS_046'])
        if spans_appr > 0:
            akind = KINDS.get(r['APPR_KIND_044A'].strip(), 'Other')
            atype = TYPES.get(r['APPR_TYPE_044B'].strip().zfill(2), 'Other')
        else:
            akind = atype = 'None'
        county = CA_COUNTIES.get(r['COUNTY_CODE_003'].strip().zfill(3), 'Unknown')
        cond = CONDITIONS.get(r['BRIDGE_CONDITION'].strip(), 'Not rated')
        snum = r['STRUCTURE_NUMBER_008'].strip()
        feature = ' '.join(r['FEATURES_DESC_006A'].split())
        facility = ' '.join(r['FACILITY_CARRIED_007'].split())
        year_recon = to_int(r['YEAR_RECONSTRUCTED_106'])
        skew = to_int(r['DEGREES_SKEW_034'])
        k43a, k43b = r['STRUCTURE_KIND_043A'].strip(), r['STRUCTURE_TYPE_043B'].strip()
        hazus = hazus_bridges.classify(
            r['STATE_CODE_001'].strip() == '06', to_int(r['YEAR_BUILT_027']),
            int(k43a) if k43a.isdigit() else 0, int(k43b) if k43b.isdigit() else 0,
            to_int(r['MAIN_UNIT_SPANS_045']), to_float(r['MAX_SPAN_LEN_MT_048']), to_float(r['STRUCTURE_LEN_MT_049']))

        table.append({
            'structure_number': snum,
            'latitude': round(lat, 6) if located else '',
            'longitude': round(lng, 6) if located else '',
            'county': county, 'feature_intersected': feature, 'facility_carried': facility,
            'location': ' '.join(r['LOCATION_009'].split()),
            'year_built': to_int(r['YEAR_BUILT_027']), 'year_reconstructed': year_recon or '',
            'lanes_on': to_int(r['TRAFFIC_LANES_ON_028A']), 'lanes_under': to_int(r['TRAFFIC_LANES_UND_028B']),
            'adt': to_int(r['ADT_029']), 'adt_year': to_int(r['YEAR_ADT_030']),
            'future_adt': to_int(r['FUTURE_ADT_114']), 'future_adt_year': to_int(r['YEAR_OF_FUTURE_ADT_115']),
            'main_material': kind, 'main_design': typ,
            'approach_material': akind, 'approach_design': atype,
            'main_spans': to_int(r['MAIN_UNIT_SPANS_045']), 'approach_spans': spans_appr,
            'max_span_m': to_float(r['MAX_SPAN_LEN_MT_048']), 'structure_length_m': to_float(r['STRUCTURE_LEN_MT_049']),
            'deck_condition': r['DECK_COND_058'].strip(), 'superstructure_condition': r['SUPERSTRUCTURE_COND_059'].strip(),
            'substructure_condition': r['SUBSTRUCTURE_COND_060'].strip(), 'channel_condition': r['CHANNEL_COND_061'].strip(),
            'culvert_condition': r['CULVERT_COND_062'].strip(), 'overall_condition': cond,
            'skew_deg': skew, 'hazus_class': f'HWB{hazus}',
        })
        if not located:
            no_location += 1
            continue
        rows.append([
            round(lat, 6), round(lng, 6), snum, to_int(r['YEAR_BUILT_027']), year_recon,
            to_int(r['TRAFFIC_LANES_ON_028A']), to_int(r['TRAFFIC_LANES_UND_028B']),
            to_int(r['ADT_029']), to_int(r['YEAR_ADT_030']), to_int(r['FUTURE_ADT_114']),
            to_int(r['YEAR_OF_FUTURE_ADT_115']),
            index(kinds, kind), index(types, typ), index(kinds, akind), index(types, atype),
            to_float(r['MAX_SPAN_LEN_MT_048']), to_int(r['MAIN_UNIT_SPANS_045']), spans_appr,
            to_float(r['STRUCTURE_LEN_MT_049']),
            rating(r['DECK_COND_058']), rating(r['SUPERSTRUCTURE_COND_059']), rating(r['SUBSTRUCTURE_COND_060']),
            rating(r['CHANNEL_COND_061']), rating(r['CULVERT_COND_062']),
            cond, index(counties, county), feature, facility, skew, hazus,
        ])

    import datetime, hashlib
    with open(path, 'rb') as f:
        source_sha256 = hashlib.sha256(f.read()).hexdigest()
    provenance = {
        'source_file': os.path.basename(path), 'source_sha256': source_sha256,
        'source_url': 'https://www.fhwa.dot.gov/bridge/nbi/ascii.cfm',
        'generated_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'generator': 'tools/build_bridges.py', 'made_by': 'E. Taciroglu', 'records_read': len(records), 'records_without_location': no_location,
        'fragility_classes': 'HAZUS highway bridge classes, see data/fragility/hazus_highway_bridges.json',
        'details': 'data/provenance.json and the Methods page of the site',
    }
    out = {'source': 'FHWA National Bridge Inventory', 'source_year': source_year, 'state': 'California',
           'provenance': provenance,
           'fields': fields, 'kinds': kinds, 'types': types, 'counties': counties, 'rows': rows}
    os.makedirs('data', exist_ok=True)
    with open('data/bridges.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'), ensure_ascii=False)
    with open('data/nbi_bridges.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(table[0].keys()))
        w.writeheader()
        w.writerows(table)

    print(f"source year: {source_year}")
    print(f"records read: {len(records)}  kept: {len(table)}  on map: {len(rows)}  without usable location: {no_location}")
    print(f"data/bridges.json: {os.path.getsize('data/bridges.json'):,} bytes")
    print(f"data/nbi_bridges.csv: {os.path.getsize('data/nbi_bridges.csv'):,} bytes")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
