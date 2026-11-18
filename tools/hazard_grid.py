#!/usr/bin/env python3
"""ShakeReady hazard grid files: the format, and how a value is read at a site.

A hazard file is JSON:

  format          "shakeready-hazard-grid/1"
  id, title       identifier and display name
  kind            "probabilistic" (a hazard map with one or more probability levels)
                  or "scenario" (ground motions of one computed or recorded earthquake)
  site_condition  what the values assume about the ground, in words
  units           "g"
  scale, nodata   stored integers times `scale` give the value; `nodata` marks a node with no value
  grid            lat_min, lon_min, dlat, dlon, nlat, nlon. Values are node-registered and stored
                  row by row from south to north, each row from west to east.
  levels          a list; each has an id, a label, and `measures`: one array of nlat * nlon integers
                  per intensity measure. Measures are named PGA, SA0P3, SA1P0 (spectral acceleration
                  at 0.3 s and 1.0 s, 5% damping).
  source          where the values came from (title, publisher, url, doi, version, retrieved, checksums)

Reading a value at a site (decisions DMG-01 and DMG-02 on the Methods page):
  bilinear interpolation between the four surrounding nodes. Nodes without a value are left out
  and the remaining weights rescaled. A site outside the grid, or with no valid node around it,
  has no value.
"""
import json

FORMAT = 'shakeready-hazard-grid/1'
MEASURES = ('PGA', 'SA0P3', 'SA1P0')


def load(path):
    h = json.load(open(path, encoding='utf-8'))
    if h.get('format') != FORMAT:
        raise ValueError(f"{path}: format is {h.get('format')!r}, expected {FORMAT!r}")
    return h


def validate(h):
    """Raise ValueError with a plain message if the file is not usable."""
    g = h['grid']
    n = g['nlat'] * g['nlon']
    for key in ('id', 'title', 'kind', 'site_condition', 'units', 'scale', 'nodata', 'levels', 'source'):
        if key not in h:
            raise ValueError(f"missing '{key}'")
    if h['kind'] not in ('probabilistic', 'scenario'):
        raise ValueError("kind must be 'probabilistic' or 'scenario'")
    if h['units'] != 'g':
        raise ValueError("units must be 'g'")
    if g['dlat'] <= 0 or g['dlon'] <= 0 or g['nlat'] < 2 or g['nlon'] < 2:
        raise ValueError('grid needs positive spacing and at least 2 by 2 nodes')
    if not h['levels']:
        raise ValueError('no levels')
    for lv in h['levels']:
        for m, arr in lv['measures'].items():
            if m not in MEASURES:
                raise ValueError(f"unknown measure '{m}'")
            if len(arr) != n:
                raise ValueError(f"level {lv['id']}, {m}: {len(arr)} values, expected {n}")
        if 'SA1P0' not in lv['measures']:
            raise ValueError(f"level {lv['id']} has no SA1P0")
    return True


def value_at(h, values, lat, lon):
    """Ground motion in g at (lat, lon) from one measure's array, or None."""
    g = h['grid']
    x = (lon - g['lon_min']) / g['dlon']
    y = (lat - g['lat_min']) / g['dlat']
    if x < 0 or y < 0 or x > g['nlon'] - 1 or y > g['nlat'] - 1:
        return None
    i0 = min(int(x), g['nlon'] - 2)
    j0 = min(int(y), g['nlat'] - 2)
    fx, fy = x - i0, y - j0
    total = weight = 0.0
    for dj, di, w in ((0, 0, (1 - fx) * (1 - fy)), (0, 1, fx * (1 - fy)), (1, 0, (1 - fx) * fy), (1, 1, fx * fy)):
        v = values[(j0 + dj) * g['nlon'] + (i0 + di)]
        if v != h['nodata'] and w > 0:
            total += w * v
            weight += w
    if weight <= 0:
        return None
    return total / weight * h['scale']
