#!/usr/bin/env python3
"""Checks of the regional dashboard, made in a browser, the way a person uses it. See README.md in this folder.

Part of ShakeReady. Made by E. Taciroglu.

    python3 tools/tests/test_dashboard.py            (from the repository root)

Opens a temporary copy of the site with made-up hazard layers, sets every filter of every inventory and compares what
the page reports with independent counts from the data files, compares the downloaded damage tables with
tools/damage_reference.py, and checks what is visible on screen. Exits with 1 if any check fails.
"""
import collections, contextlib, functools, http.server, json, os, re, shutil, socketserver, subprocess, sys, tempfile, threading, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import make_test_layers
from playwright.sync_api import sync_playwright

# ------------------------------------------------------------------ the site, served from a temporary copy
LIBS = os.environ.get('SR_TEST_LIBS')            # a folder holding Leaflet and Leaflet.markercluster, where the CDN cannot be reached
CDN_FILES = {'leaflet.min.js': 'leaflet.js', 'leaflet.min.css': 'leaflet.css', 'leaflet.markercluster.min.js': 'leaflet.markercluster.js',
             'MarkerCluster.min.css': 'MarkerCluster.css', 'MarkerCluster.Default.min.css': 'MarkerCluster.Default.css'}
PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360606060000000050001a5f645400000000049454e44ae426082')

def local_lib(name):
    if not LIBS or name not in CDN_FILES: return None
    for d, _, files in os.walk(LIBS):
        if CDN_FILES[name] in files and os.sep + 'dist' in d: return os.path.join(d, CDN_FILES[name])
    return None

def scratch_copy():
    """A temporary copy of the working tree with the made-up test layers. Deleted when the run ends."""
    site = os.path.join(tempfile.mkdtemp(prefix='shakeready-test-'), 'site')
    shutil.copytree(ROOT, site, ignore=shutil.ignore_patterns('.git', '__pycache__', 'libs', 'node_modules'))
    make_test_layers.write(site)
    return site

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

@contextlib.contextmanager
def serve(directory):
    handler = functools.partial(Quiet, directory=directory)
    class S(socketserver.ThreadingTCPServer):
        allow_reuse_address = True; daemon_threads = True
    srv = S(('127.0.0.1', 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    try: yield f'http://127.0.0.1:{srv.server_address[1]}'
    finally: srv.shutdown(); srv.server_close()


def route(page):
    def handle(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1'): return r.continue_()
        name = u.split('?')[0].rsplit('/', 1)[-1]
        if 'cdnjs.cloudflare.com' in u:
            path = local_lib(name)
            return r.fulfill(path=path, content_type='text/css' if name.endswith('.css') else 'application/javascript') if path else r.continue_()
        if 'tile.openstreetmap.org' in u: return r.fulfill(body=PNG, content_type='image/png')       # no map tiles are needed
        if 'fonts.googleapis.com' in u: return r.fulfill(body='', content_type='text/css')
        return r.abort()                                                                              # photographs and anything else
    page.route('**/*', handle)

@contextlib.contextmanager
def browser_page(directory, path='dashboard.html', width=1280, height=900, wait="() => typeof B !== 'undefined' && B && document.getElementById('map')"):
    with serve(directory) as base, sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={'width': width, 'height': height}, accept_downloads=True).new_page()
        page.errors = []
        page.on('pageerror', lambda e: page.errors.append(str(e)))
        page.on('console', lambda m: page.errors.append('console: ' + m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
        route(page)
        page.goto(f'{base}/{path}')
        if wait: page.wait_for_function(wait, timeout=60000)
        try: yield page
        finally: b.close()

# ------------------------------------------------------------------ the reference damage tables
def reference(site, hazard, level=None):
    cmd = [sys.executable, 'tools/damage_reference.py', f'hazards/{hazard}.json'] + ([level] if level else [])
    return subprocess.run(cmd, cwd=site, capture_output=True, text=True, check=True).stdout

def body(csv_text):
    return [l for l in csv_text.splitlines() if not l.startswith('#')]

def compare(site, tables, verbose=True):
    ok = True
    refs = {}
    for key, text in tables.items():
        parts = key.split('/')
        hz, lv = parts[0], (None if parts[1] == 'None' else parts[1])
        if (hz, lv) not in refs: refs[(hz, lv)] = reference(site, hz, lv).splitlines()
        ref, got = refs[(hz, lv)], body(text)
        if len(parts) > 2:      # a filtered download: the reference rows for that county, in the same order
            county = parts[2]
            ci = ref[0].split(',').index('county')
            ref = [ref[0]] + [l for l in ref[1:] if l.split(',')[ci].lower() == county]
        same = ref == got
        ok &= same
        blanks = sum(1 for l in got[1:] if ',,,' in l)
        if verbose: print(f'  {key:34} dashboard rows {len(got) - 1:6}  reference rows {len(ref) - 1:6}  identical: {same}  (rows outside the layer: {blanks})')
        if not same:
            for i, (a, b) in enumerate(zip(ref, got)):
                if a != b: print('   first difference at row', i, '\n    ref:', a[:300], '\n    got:', b[:300]); break
    return ok


# ------------------------------------------------------------------ the checks
fails, passed = [], [0]
def check(name, ok, detail=''):
    if ok: passed[0] += 1
    else: fails.append(f'{name}: {detail}'); print('   FAIL', name, detail)

SITE = scratch_copy()

# ------------------------------------------------------------------ what a person does
def open_section(page, key):
    if page.get_attribute(f'#inv-{key} .inv-toggle', 'aria-expanded') != 'true': page.click(f'#inv-{key} .inv-toggle')
    page.evaluate("key => document.querySelectorAll(`#inv-${key} details`).forEach(d => { if (!d.open) d.querySelector('summary').click(); })", key)
def tick(page, key, label):
    page.locator(f'#inv-{key} .frow label').filter(has_text=re.compile(r'^\s*' + re.escape(label) + r'(\s*\([\d,]+\))?\s*$')).locator('input').check()
def do(page, key, actions):
    page.click(f'#inv-{key} .btn-reset')
    for a in actions:
        if a[0] == 'range':
            if a[2] is not None: page.fill(f'#f-{key}-{a[1]}-1', a[2])
            if a[3] is not None: page.fill(f'#f-{key}-{a[1]}-2', a[3])
        elif a[0] == 'select': page.select_option(f'#f-{key}-{a[1]}', label=a[2])
        elif a[0] == 'select_prefix':
            texts = page.evaluate("id => [...document.getElementById(id).options].map(o => o.textContent)", f'f-{key}-{a[1]}')
            hit = [t for t in texts if t.startswith(a[2])]; assert len(hit) == 1, (a, hit)
            page.select_option(f'#f-{key}-{a[1]}', label=hit[0])
        elif a[0] == 'tick': tick(page, key, a[1])
        elif a[0] == 'text': page.fill(f'#f-{key}-{a[1]}', a[2])
    page.click(f'#inv-{key} .btn-apply')
def shown(page, key):
    m = re.search(r'([\d,]+)\s+of\s+([\d,]+)', page.inner_text(f'#inv-{key} .inv-shown'))
    return int(m.group(1).replace(',', '')), int(m.group(2).replace(',', ''))
num = lambda v: None if v in (None, '') else float(v)

# ------------------------------------------------------------------ bridges: the same 30 settings as before the change
bd = json.load(open(f'{SITE}/data/bridges.json')); F = {f: i for i, f in enumerate(bd['fields'])}; R = bd['rows']
g = lambda r, f: r[F[f]]
county = lambda r: bd['counties'][g(r, 'county_i')]
kind = lambda r: bd['kinds'][g(r, 'kind_i')]
BRIDGE = {
 'none': ([], lambda r: True),
 'year_built_1960_1975': ([('range', 'yb', '1960', '1975')], lambda r: 1960 <= g(r, 'year_built') <= 1975),
 'year_built_from_2000': ([('range', 'yb', '2000', None)], lambda r: g(r, 'year_built') >= 2000),
 'year_built_to_1930': ([('range', 'yb', None, '1930')], lambda r: g(r, 'year_built') <= 1930),
 'year_recon_1990_2010': ([('range', 'yr', '1990', '2010')], lambda r: g(r, 'year_recon') and 1990 <= g(r, 'year_recon') <= 2010),
 'year_recon_from_1800': ([('range', 'yr', '1800', None)], lambda r: g(r, 'year_recon') and g(r, 'year_recon') >= 1800),
 'lanes_4_8': ([('range', 'ln', '4', '8')], lambda r: 4 <= g(r, 'lanes_on') <= 8),
 'lanes_0_0': ([('range', 'ln', '0', '0')], lambda r: g(r, 'lanes_on') == 0),
 'adt_min_100000': ([('range', 'adt', '100000', None)], lambda r: g(r, 'adt') >= 100000),
 'adt_max_500': ([('range', 'adt', None, '500')], lambda r: g(r, 'adt') <= 500),
 'span_30p5_60': ([('range', 'sp', '30.5', '60')], lambda r: 30.5 <= g(r, 'max_span') <= 60),
 'span_min_300': ([('range', 'sp', '300', None)], lambda r: g(r, 'max_span') >= 300),
 'nspans_3_5': ([('range', 'ns', '3', '5')], lambda r: 3 <= g(r, 'spans_main') <= 5),
 'nspans_max_1': ([('range', 'ns', None, '1')], lambda r: g(r, 'spans_main') <= 1),
 'county_los_angeles': ([('select', 'county', 'Los Angeles')], lambda r: county(r) == 'Los Angeles'),
 'county_alpine': ([('select', 'county', 'Alpine')], lambda r: county(r) == 'Alpine'),
 'hazus_3': ([('select_prefix', 'hazus', 'HWB3 (')], lambda r: g(r, 'hazus') == 3),
 'hazus_10': ([('select_prefix', 'hazus', 'HWB10 (')], lambda r: g(r, 'hazus') == 10),
 'hazus_28': ([('select_prefix', 'hazus', 'HWB28 (')], lambda r: g(r, 'hazus') == 28),
 'cond_poor': ([('tick', 'Poor')], lambda r: g(r, 'cond') == 'Poor'),
 'cond_good_fair': ([('tick', 'Good'), ('tick', 'Fair')], lambda r: g(r, 'cond') in ('Good', 'Fair')),
 'deck_0_4': ([('range', '9-dk', '0', '4')], lambda r: 0 <= g(r, 'deck') <= 4),
 'super_min_8': ([('range', '9-su', '8', None)], lambda r: g(r, 'superstructure') >= 8),
 'sub_max_3': ([('range', '9-sb', None, '3')], lambda r: 0 <= g(r, 'substructure') <= 3),
 'channel_5_6': ([('range', '9-ch', '5', '6')], lambda r: 5 <= g(r, 'channel') <= 6),
 'culvert_min_0': ([('range', '9-cv', '0', None)], lambda r: g(r, 'culvert') >= 0),
 'material_steel': ([('tick', 'Steel')], lambda r: kind(r) == 'Steel'),
 'material_two': ([('tick', 'Concrete'), ('tick', 'Wood or Timber')], lambda r: kind(r) in ('Concrete', 'Wood or Timber')),
 'material_masonry': ([('tick', 'Masonry')], lambda r: kind(r) == 'Masonry'),
 'combo': ([('range', 'yb', '1950', '1980'), ('select', 'county', 'San Diego'), ('tick', 'Fair'), ('range', 'ns', '2', None), ('tick', 'Continuous Prestressed Concrete'), ('tick', 'Prestressed Concrete')],
           lambda r: 1950 <= g(r, 'year_built') <= 1980 and county(r) == 'San Diego' and g(r, 'cond') == 'Fair' and g(r, 'spans_main') >= 2 and kind(r) in ('Continuous Prestressed Concrete', 'Prestressed Concrete')),
}

# ------------------------------------------------------------------ buildings: settings and independent counts
CS = [f['properties'] for f in json.load(open(f'{SITE}/data/csmip_instrumented_buildings.geojson'))['features']]
LT = [f['properties'] for f in json.load(open(f'{SITE}/data/latimes_concrete_buildings.geojson'))['features']]
has = lambda p, fields, *words: all(w in '\n'.join(str(p[f]) for f in fields if p.get(f) not in (None, '')).lower() for w in words)
between = lambda v, lo, hi: v is not None and (lo is None or v >= lo) and (hi is None or v <= hi)
ND = 'Instrumented Non-Ductile Buildings'
CSMIP = {
 'none': ([], lambda p: True),
 'name_hospital': ([('text', 'q', 'hospital')], lambda p: has(p, ('name', 'address'), 'hospital')),
 'name_los_angeles': ([('text', 'q', 'los angeles')], lambda p: has(p, ('name', 'address'), 'los', 'angeles')),
 'name_caps_spaces': ([('text', 'q', '  PARKING   Los ')], lambda p: has(p, ('name', 'address'), 'parking', 'los')),
 'name_nothing': ([('text', 'q', 'zzzz')], lambda p: False),
 'list_nonductile': ([('tick', 'Instrumented non-ductile buildings')], lambda p: p['original_layer'] == ND),
 'list_general': ([('tick', 'Instrumented buildings')], lambda p: p['original_layer'] != ND),
 'list_both': ([('tick', 'Instrumented buildings'), ('tick', 'Instrumented non-ductile buildings')], lambda p: True),
 'stories_8_up': ([('range', 'st', '8', None)], lambda p: between(p['stories'], 8, None)),
 'stories_1_3': ([('range', 'st', '1', '3')], lambda p: between(p['stories'], 1, 3)),
 'stories_to_100': ([('range', 'st', None, '100')], lambda p: p['stories'] is not None),
 'design_to_1975': ([('range', 'dy', None, '1975')], lambda p: between(p['design_year'], None, 1975)),
 'design_1960_1970': ([('range', 'dy', '1960', '1970')], lambda p: between(p['design_year'], 1960, 1970)),
 'basement_none': ([('tick', 'None')], lambda p: p['Basement'] == '0'),
 'basement_one_two': ([('tick', 'One'), ('tick', 'Two')], lambda p: p['Basement'] in ('1', '2')),
 'basement_partial': ([('tick', 'Partial')], lambda p: p['Basement'] == 'partial'),
 'plan_rectangular': ([('select_prefix', 'plan', 'Rectangular (')], lambda p: p['Plan Shape'] == 'Rectangular'),
 'plan_l': ([('select_prefix', 'plan', 'L-shaped (')], lambda p: p['Plan Shape'] == 'L-shaped'),
 'plan_not_recorded': ([('select_prefix', 'plan', 'Not recorded (')], lambda p: p['Plan Shape'] is None),
 'instr_year_1990_up': ([('range', '6-iy', '1990', None)], lambda p: between(p['instrumented_year'], 1990, None)),
 'accel_16_up': ([('range', '6-ac', '16', None)], lambda p: between(p['accelerometers'], 16, None)),
 'levels_5_6': ([('range', '6-lv', '5', '6')], lambda p: between(p['instrumented_levels'], 5, 6)),
 'free_field_yes': ([('tick', 'Mentioned')], lambda p: p['free_field'] is True),
 'free_field_no': ([('tick', 'Not mentioned')], lambda p: p['free_field'] is False),
 'combo': ([('tick', 'Instrumented non-ductile buildings'), ('range', 'st', '8', None), ('range', '6-ac', '14', None)], lambda p: p['original_layer'] == ND and between(p['stories'], 8, None) and between(p['accelerometers'], 14, None)),
}
LATIMES = {
 'none': ([], lambda p: True),
 'q_wilshire': ([('text', 'q', 'wilshire')], lambda p: has(p, ('address', 'building_name', 'zip_code'), 'wilshire')),
 'q_park_la_brea': ([('text', 'q', 'Park La Brea')], lambda p: has(p, ('address', 'building_name', 'zip_code'), 'park', 'la', 'brea')),
 'q_zip': ([('text', 'q', '90014')], lambda p: has(p, ('address', 'building_name', 'zip_code'), '90014')),
 'type_c2l': ([('tick', 'C2L')], lambda p: p['hazus'] == 'C2L'),
 'type_c3m_c3h': ([('tick', 'C3M'), ('tick', 'C3H')], lambda p: p['hazus'] in ('C3M', 'C3H')),
 'level_pre': ([('tick', 'Pre-Code')], lambda p: p['level'] == 'PC'),
 'level_low': ([('tick', 'Low-Code')], lambda p: p['level'] == 'LC'),
 'stories_8_up': ([('range', 'st', '8', None)], lambda p: between(num(p['stories']), 8, None)),
 'stories_1_3': ([('range', 'st', '1', '3')], lambda p: between(num(p['stories']), 1, 3)),
 'year_to_1933': ([('range', 'yb', None, '1933')], lambda p: between(num(p['yrblt']), None, 1933)),
 'year_1950_1976': ([('range', 'yb', '1950', '1976')], lambda p: between(num(p['yrblt']), 1950, 1976)),
 'year_any_recorded': ([('range', 'yb', '1000', None)], lambda p: num(p['yrblt']) is not None),
 'update_demolished': ([('select_prefix', 'update', 'Recorded as demolished (')], lambda p: 'demolished' in (p['Update'] or '').lower()),
 'update_not_demolished': ([('select_prefix', 'update', 'Not recorded as demolished (')], lambda p: 'demolished' not in (p['Update'] or '').lower()),
 'update_has_note': ([('select_prefix', 'update', 'Has an update note (')], lambda p: bool(p['Update'])),
 'update_no_note': ([('select_prefix', 'update', 'No update note (')], lambda p: not p['Update']),
 'use_not_recorded': ([('select_prefix', 'use', 'Not recorded (')], lambda p: not p['name']),
 'combo': ([('select_prefix', 'class', 'C3H-PC ('), ('range', 'st', '10', None), ('text', 'q', 'spring')], lambda p: p['hazus_fragility_class'] == 'C3H-PC' and between(num(p['stories']), 10, None) and has(p, ('address', 'building_name', 'zip_code'), 'spring')),
}
for c in sorted(set(p['hazus_fragility_class'] for p in LT)): LATIMES['class_' + c] = ([('select_prefix', 'class', c + ' (')], (lambda c: lambda p: p['hazus_fragility_class'] == c)(c))
for u in sorted(set(p['name'] for p in LT if p['name'])): LATIMES['use_' + u] = ([('select_prefix', 'use', u + ' (')], (lambda u: lambda p: p['name'] == u)(u))

def run_cases(page, key, cases, records, label):
    open_section(page, key)
    t0 = time.time(); n_zero = 0
    for name, (actions, pred) in cases.items():
        do(page, key, actions)
        got, total = shown(page, key); want = sum(1 for r in records if pred(r))
        n_zero += want == 0
        check(f'{label} {name}', got == want and total == len(records), f'page {got} of {total}, independent count {want} of {len(records)}')
        if key != 'nbi-bridges':                                           # what Leaflet has on the map is the same selection
            on_map = page.evaluate("id => { const s = INV.find(x => x.inv.id === id); return [s.layer.getLayers().length, map.hasLayer(s.layer), s.box.checked]; }", key)
            check(f'{label} {name} on the map', on_map == [want, True, True], f'{on_map} vs {want}')
    page.click(f'#inv-{key} .btn-reset')
    print(f'{label}: {len(cases)} settings in {time.time() - t0:.0f} s ({n_zero} of them select nothing)')

def download(page, hazard, level=None):
    page.click('#tab-hazard')
    if page.input_value('#hazard') != hazard: page.select_option('#hazard', value=hazard)
    page.wait_for_function("id => HAZ && HAZ.id === id && DMG.size === B.rows.length", arg=hazard, timeout=60000)
    page.wait_for_load_state('networkidle')
    want = level or page.evaluate("HAZ.default_level")
    if page.input_value('#hazlevel') != want: page.select_option('#hazlevel', value=want)
    page.wait_for_function("id => LEVEL && LEVEL.id === id", arg=want)
    page.click('#tab-damage')
    with page.expect_download() as d: page.click('#dmg-download')
    return open(d.value.path(), encoding='utf-8').read()
body = lambda t: [l for l in t.splitlines() if not l.startswith('#')]
head = lambda t: [l for l in t.splitlines() if l.startswith('#')]

def run():
    with browser_page(SITE) as page:
        page.wait_for_function("INV.length === 3 && INV.every(s => s.ready)", timeout=60000)
        # ---- what a first-time visitor sees
        vis = page.evaluate("INV.map(s => [s.count.textContent, s.toggle.getAttribute('aria-expanded'), s.box.checked])")
        check('counts at start', vis == [['25,974 bridges', 'false', True], ['61 buildings', 'false', False], ['1,451 buildings', 'false', False]], vis)
        for key in ('nbi-bridges', 'csmip-buildings', 'latimes-concrete'):
            check(f'{key} closed at start', not page.is_visible(f'#inv-{key}-body') and page.locator(f'#inv-{key}-body input:visible, #inv-{key}-body select:visible').count() == 0)
            page.click(f'#inv-{key} .inv-toggle')
            check(f'{key} opens', page.is_visible(f'#inv-{key}-body') and page.is_visible(f'#inv-{key} .btn-apply') and not page.is_visible(f'#inv-{key} .inv-pending'))
            page.click(f'#inv-{key} .inv-toggle')
            check(f'{key} closes again', not page.is_visible(f'#inv-{key}-body') and not page.is_visible(f'#inv-{key} .btn-apply'))
        check('tab note at start', page.inner_text('#tabsub-inventory') == '25,974 bridges', page.inner_text('#tabsub-inventory'))
        # ---- the bridge filters offer what they offered before
        open_section(page, 'nbi-bridges')
        opt = lambda fid: page.evaluate("id => [...document.getElementById(id).options].map(o => o.textContent)", fid)
        check('county list', opt('f-nbi-bridges-county') == ['Any county'] + sorted(bd['counties']), opt('f-nbi-bridges-county')[:4])
        hz = json.load(open(f'{SITE}/data/fragility/hazus_highway_bridges.json'))['classes']; n_in = collections.Counter(g(r, 'hazus') for r in R)
        check('class list', opt('f-nbi-bridges-hazus') == ['Any class'] + [f'HWB{k} ({n_in[k]:,}): ' + hz[f'HWB{k}']['description'] for k in sorted(n_in)], opt('f-nbi-bridges-hazus')[:3])
        mats = page.evaluate("[...document.querySelectorAll('#inv-nbi-bridges .checkgrid label')].map(l => l.textContent.trim())")
        check('materials', mats == [k for k in bd['kinds'] if k != 'None'], mats)
        labels = page.evaluate("[...document.querySelectorAll('#inv-nbi-bridges .frow > label, #inv-nbi-bridges .flabel, #inv-nbi-bridges summary')].map(l => l.textContent.trim())")
        check('bridge filter names', labels == ['Year built', 'Year reconstructed', 'Traffic lanes on bridge', 'Average daily traffic', 'Longest span, meters', 'Number of main spans', 'County', 'HAZUS fragility class', 'Overall condition', 'Component condition ratings (0 to 9)', 'Deck', 'Superstructure', 'Substructure', 'Channel', 'Culvert', 'Main structure material'], labels)
        run_cases(page, 'nbi-bridges', BRIDGE, R, 'bridges')
        # ---- changed but not applied: nothing moves until Apply; Enter applies
        page.fill('#f-nbi-bridges-yb-1', '2000')
        check('a change not applied is announced', page.is_visible('#inv-nbi-bridges .inv-pending'))
        check('a change not applied changes nothing', page.evaluate("BR.shown.length") == 25974 and shown(page, 'nbi-bridges')[0] == 25974)
        page.press('#f-nbi-bridges-yb-1', 'Enter')
        check('Enter applies', shown(page, 'nbi-bridges')[0] == 3283 and not page.is_visible('#inv-nbi-bridges .inv-pending') and page.inner_text('#inv-nbi-bridges .inv-count') == '3,283 of 25,974 bridges', page.inner_text('#inv-nbi-bridges .inv-shown'))
        check('filters in effect are stated', 'Filters: Year built: 2000 or more' in page.inner_text('#inv-nbi-bridges .inv-shown'), page.inner_text('#inv-nbi-bridges .inv-shown'))
        check('tab note when filtered', page.inner_text('#tabsub-inventory') == '3,283 of 25,974', page.inner_text('#tabsub-inventory'))
        page.click('#inv-nbi-bridges .btn-reset')
        check('Reset restores all', shown(page, 'nbi-bridges')[0] == 25974 and page.input_value('#f-nbi-bridges-yb-1') == '' and page.inner_text('#inv-nbi-bridges .inv-count') == '25,974 bridges')
        page.click('#inv-nbi-bridges .inv-toggle')
        # ---- buildings
        check('applying to a hidden inventory', page.evaluate("INV[1].box.checked") is False)
        run_cases(page, 'csmip-buildings', CSMIP, CS, 'CSMIP')
        check('tab note with two shown', page.inner_text('#tabsub-inventory') == '2 inventories', page.inner_text('#tabsub-inventory'))
        # every plan-shape option states the count an independent count gives
        plan = opt('f-csmip-buildings-plan')[1:]
        want = collections.Counter(p['Plan Shape'] or 'Not recorded' for p in CS)
        check('plan shape options', sorted(plan) == sorted(f'{k} ({v})' for k, v in want.items()) and plan[0] == 'Rectangular (48)', plan)
        # ---- the six on the map: drawn where they are, in the inventory's color
        do(page, 'csmip-buildings', [('tick', 'Instrumented non-ductile buildings')])
        page.click('#inv-csmip-buildings [data-zoom]'); page.wait_for_timeout(900)
        px = page.evaluate("""() => { const s = INV[1], out = [];
            for (const m of s.layer.getLayers()){ const pt = map.latLngToContainerPoint(m.getLatLng()), r = map.getRenderer(m), c = r._container, k = c.width / c.clientWidth, box = c.getBoundingClientRect(), mb = map.getContainer().getBoundingClientRect();
              const d = r._ctx.getImageData(Math.round((pt.x + mb.left - box.left) * k), Math.round((pt.y + mb.top - box.top) * k), 1, 1).data;
              out.push([map.getBounds().contains(m.getLatLng()), d[0], d[1], d[2], d[3]]); } return out; }""")
        check('six drawn in view after "Zoom to them"', len(px) == 6 and all(p[0] for p in px), px)
        check('six painted in the inventory color', all(abs(p[1] - 0x3D) < 40 and abs(p[2] - 0x9B) < 40 and abs(p[3] - 0xE9) < 40 and p[4] > 150 for p in px), px)
        pop = page.evaluate("""() => { const m = INV[1].layer.getLayers().find(m => m.feature.properties.station_number === '24581'); m.openPopup(); const el = document.querySelector('.leaflet-popup-content'); return [el.innerText, [...el.querySelectorAll('a')].map(a => [a.textContent, a.href])]; }""")
        check('CSMIP popup', pop[0].startswith('Los Angeles - 12-story Comm./Office Bldg') and 'Address: 818 West 7th Street' in pop[0] and 'CSMIP station: 24581' in pop[0] and 'List on the original site: Instrumented Non-Ductile Buildings' in pop[0] and 'Stories: 12\n' in pop[0] and 'Basement levels: 2\n' in pop[0]
              and ['Open the CESMD station page', 'http://www.strongmotioncenter.org/cgi-bin/CESMD/stationhtml.pl?staID=CE24581&network=CGS'] in pop[1] and any(t == 'Open Street View' for t, h in pop[1]), pop)
        page.evaluate("() => { map.closePopup(); }")
        page.uncheck('#lyr-csmip-buildings')
        check('unticking takes it off the map', page.evaluate("map.hasLayer(INV[1].layer)") is False and 'selected. Tick the box' in page.inner_text('#inv-csmip-buildings .inv-shown') and page.inner_text('#tabsub-inventory') == '25,974 bridges')
        page.click('#inv-csmip-buildings .btn-reset'); page.click('#inv-csmip-buildings .inv-toggle')
        run_cases(page, 'latimes-concrete', LATIMES, LT, 'LA Times')
        cls = opt('f-latimes-concrete-class')
        check('LA Times class list', cls[1] == 'C2L-PC (282): Concrete shear walls, 1-3 stories, Pre-Code' and len(cls) == 13, cls[:3])
        use = opt('f-latimes-concrete-use')
        check('occupancy list', use[1] == 'Commercial (235)' and use[-1] == 'Not recorded (1)' and len(use) == 51, (use[:3], use[-1], len(use)))
        notes = page.evaluate("[...document.querySelectorAll('#inv-latimes-concrete .fnote')].map(p => p.textContent)")
        check('missing years are stated', any(n.startswith('214 buildings have no year recorded') for n in notes), notes)
        pop = page.evaluate("""() => { const m = INV[2].layer.getLayers()[0]; m.openPopup(); return document.querySelector('.leaflet-popup-content').innerText; }""")
        check('LA Times popup unchanged in form', 'HAZUS fragility class:' in pop and 'address:' in pop and 'yrblt:' in pop, pop[:200])
        page.evaluate("() => { map.closePopup(); }")
        page.uncheck('#lyr-latimes-concrete'); page.uncheck('#lyr-nbi-bridges')
        check('tab note with none shown', page.inner_text('#tabsub-inventory') == 'None shown')
        page.check('#lyr-nbi-bridges'); page.click('#inv-latimes-concrete .inv-toggle')
        # ---- damage: the tables the dashboard gives, against the reference code and against before the change
        tables = {}
        for hz, lv in (('test-map', None), ('test-map', 'rp2475'), ('test-scenario', None)): tables[f'{hz}/{lv}'] = download(page, hz, lv)
        check('legend on the map while damage is shown', page.is_visible('#map-legend'))
        page.click('#tab-inventory'); open_section(page, 'nbi-bridges'); do(page, 'nbi-bridges', [('select', 'county', 'Alameda')])
        tables['test-scenario/None/alameda'] = download(page, 'test-scenario')
        check('summary where no bridge is inside the layer', 'No estimate (outside the hazard layer)\t662' in page.inner_text('#dmg-summary'), page.inner_text('#dmg-summary')[:200])
        page.click('#tab-inventory'); do(page, 'nbi-bridges', [('select', 'county', 'Los Angeles')])
        tables['test-scenario/None/los angeles'] = download(page, 'test-scenario')
        report = page.get_attribute('#dmg-report', 'href')
        print('damage tables against the reference code:')
        check('damage tables equal the reference', compare(SITE, tables))
        h_all, h_la = head(tables['test-map/None']), head(tables['test-scenario/None/los angeles'])
        check('table header states no filters', '# Filters in effect: none' in h_all and any(l.startswith('# Bridges: 25974 of 25974') for l in h_all), [l for l in h_all if 'Bridges' in l or 'Filters' in l])
        check('table header states the filter', '# Filters in effect: County: Los Angeles' in h_la and any(l.startswith('# Bridges: 3549 of 25974') for l in h_la), [l for l in h_la if 'Bridges' in l or 'Filters' in l])
        ctx = urllib.parse.parse_qs(urllib.parse.urlparse(report).query)['context'][0]
        check('report link carries the selection', 'Bridges: 3,549 of 25,974; filters: County: Los Angeles' in ctx, ctx)
        check('no page errors', not page.errors, page.errors)


if __name__ == '__main__':
    try:
        run()
    finally:
        shutil.rmtree(os.path.dirname(SITE), ignore_errors=True)        # the made-up layers go with it
    print(f'\n{passed[0]} checks passed, {len(fails)} failed')
    for f in fails: print('  FAILED:', f[:400])
    sys.exit(1 if fails else 0)
