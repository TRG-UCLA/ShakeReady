#!/usr/bin/env python3
"""Write data/provenance.json: where each published data file came from, what was done to it,
the choices that were made, what was checked, and a checksum of every file.

Static facts (sources, retrieval dates, source checksums, processing steps) are in
tools/provenance_sources.json. This script adds what can be computed: the checksum, size and
record count of each published file, and how many bridges each HAZUS decision affects.

Usage, from the repository root, after rebuilding any data file:
    python3 tools/build_provenance.py
"""
import csv, datetime, hashlib, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hazus_bridges as hz


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def record_count(path):
    if path.endswith('.csv'):
        with open(path, newline='', encoding='utf-8') as f:
            return sum(1 for _ in csv.reader(f)) - 1
    d = json.load(open(path, encoding='utf-8'))
    if 'rows' in d: return len(d['rows'])
    if 'features' in d: return len(d['features'])
    if 'classes' in d: return len(d['classes'])
    return None


def decision_effects():
    d = json.load(open('data/bridges.json', encoding='utf-8'))
    F = {f: i for i, f in enumerate(d['fields'])}
    R = d['rows']
    cls = lambda r: hz.CLASSES[r[F['hazus']]]
    n = lambda cond: sum(1 for r in R if cond(r))
    fmt = lambda v: f'{v:,}'
    b_is_one = lambda r: cls(r)['k3d'] and hz.K3D_COEFFICIENTS[cls(r)['k3d']][1] == 1
    culv = [r for r in R if d['types'][r[F['type_i']]] == 'Culvert']
    return {
        'HZ-01': f"{fmt(n(lambda r: 1975 <= r[F['year_built']] <= 1989))} bridges built from 1975 to 1989 are classed as seismic design; under the other reading they would be conventional.",
        'HZ-02': f"Applies to the {fmt(n(lambda r: r[F['spans_main']] > 1 and cls(r)['k3d']))} bridges with more than one span and a K3D equation.",
        'HZ-03': f"{fmt(n(lambda r: r[F['spans_main']] == 1 and b_is_one(r)))} single-span bridges.",
        'HZ-04': f"{fmt(n(lambda r: r[F['hazus']] == 28))} bridges in HWB28.",
        'HZ-05': f"{fmt(n(lambda r: r[F['spans_appr']] > 0))} bridges have approach spans that are not counted.",
        'HZ-06': f"Decides the class of {fmt(n(lambda r: r[F['hazus']] in (13, 25, 15, 27)))} steel bridges, of which {fmt(n(lambda r: r[F['hazus']] in (25, 27)))} are under 20 m.",
        'HZ-07': f"{fmt(n(lambda r: r[F['skew']] == 99))} bridges have skew coded 99.",
        'HZ-08': f"All {fmt(len(R))} bridges.",
        'HZ-09': f"{fmt(len(culv))} culverts: " + ', '.join(f"{fmt(sum(1 for r in culv if r[F['hazus']] == k))} in HWB{k}" for k in sorted(set(r[F['hazus']] for r in culv))) + '.',
        'HZ-10': f"{fmt(n(lambda r: cls(r)['design'] == 'Conventional'))} bridges are classed as conventional design; {fmt(n(lambda r: cls(r)['design'] == 'Conventional' and r[F['year_recon']] > 0))} of them have a reconstruction year on record.",
        'HZ-11': f"{fmt(n(lambda r: cls(r)['ishape'] == 1))} bridges are in classes where the factor can apply.",
    }, {
        'NBI-02': f"{fmt(json.load(open('data/bridges.json'))['provenance']['records_without_location'])} record is listed without coordinates." if 'provenance' in d else None,
        'class_counts': {f'HWB{k}': sum(1 for r in R if r[F['hazus']] == k) for k in sorted(set(r[F['hazus']] for r in R))},
        'on_map': len(R),
    }


def hazard_layers():
    """The published hazard layers, with a fresh checksum of each file."""
    path = 'hazards/index.json'
    if not os.path.exists(path):
        return []
    out = []
    for h in json.load(open(path, encoding='utf-8')).get('hazards', []):
        h = dict(h)
        if os.path.exists(h['file']):
            h['sha256'], h['bytes'] = sha256(h['file']), os.path.getsize(h['file'])
        out.append(h)
    return out


def tools():
    """Outside tools this site uses unchanged, with the release in use."""
    path = 'hazardmaker/lib/VERSION.json'
    if not os.path.exists(path):
        return {}
    v = json.load(open(path, encoding='utf-8'))
    for f, digest in v['files'].items():
        if sha256(f) != digest:
            raise SystemExit(f'{f} differs from the SR-HazardMaker release it was copied from. Run tools/sync_hazardmaker.py; do not edit the copy.')
    return {v['tool']: {k: v[k] for k in ('repository', 'tag', 'commit', 'synced_utc', 'files')}}


def main():
    src = json.load(open('tools/provenance_sources.json', encoding='utf-8'))
    effects, extra = decision_effects()
    for ds in src['datasets']:
        ds['published_files'] = [{'path': p, 'sha256': sha256(p), 'bytes': os.path.getsize(p), 'records': record_count(p)} for p in ds.pop('files')]
    frag = json.load(open('data/fragility/hazus_highway_bridges.json', encoding='utf-8'))
    for dec in src['inventory_decisions']:
        if dec['id'] in extra and extra[dec['id']]:
            dec['effect'] = extra[dec['id']]
    try:
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        commit = None
    out = {
        'about': 'Provenance of the data published by ShakeReady: sources, processing, recorded decisions, checks and file checksums.',
        'release': src['release'],
        'generated_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'repository': src['repository'],
        'code_version': commit,
        'code_version_note': 'The repository commit in place when this file was generated. The commit that publishes this file is the next one.',
        'prepared_by': src['prepared_by'],
        'sources': src['sources'],
        'datasets': src['datasets'],
        'fragility_decisions': [dict(d, effect=effects.get(d['id'])) for d in frag['decisions']],
        'inventory_decisions': src['inventory_decisions'],
        'damage_decisions': src.get('damage_decisions', []),
        'hazard_decisions': src.get('hazard_decisions', []),
        'hazard_layers': hazard_layers(),
        'tools': tools(),
        'hazus_class_counts': extra['class_counts'],
        'verification': src['verification'],
        'limits': src['limits'],
    }
    with open('data/provenance.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print('wrote data/provenance.json:', len(out['datasets']), 'datasets,', len(out['fragility_decisions']) + len(out['inventory_decisions']) + len(out['damage_decisions']) + len(out['hazard_decisions']), 'decisions,', len(out['hazard_layers']), 'hazard layers')


if __name__ == '__main__':
    main()
