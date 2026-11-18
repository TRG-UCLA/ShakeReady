# Hazard layers

This folder is ShakeReady's repository of hazard layers: gridded ground motions that the map can
display and use to estimate damage. `index.json` lists the layers the map offers. Each layer is
one JSON file in this folder.

There are two kinds:

- **probabilistic**: a hazard map, with one or more probability levels (for example the USGS National
  Seismic Hazard Model at 475, 975 and 2,475 years). Each place is given the shaking with a set chance of
  being exceeded there. It is not one earthquake, so results should not be added up across assets as if it were.
- **scenario**: the ground motions of one earthquake, either computed (a simulation) or recorded (for
  example a USGS ShakeMap).

## File format

`"format": "shakeready-hazard-grid/1"`. The full description is in SR-HazardMaker's `docs/format.md`. In short:

| Field | Meaning |
|---|---|
| `id`, `title` | identifier (also the file name) and display name |
| `kind` | `probabilistic` or `scenario` |
| `site_condition` | what the values assume about the ground, in words, e.g. "Vs30 = 760 m/s" or "site-specific, as computed" |
| `units`, `scale`, `nodata` | units are `g`; stored integers times `scale` give the value; `nodata` marks a node with no value |
| `grid` | `lat_min`, `lon_min`, `dlat`, `dlon`, `nlat`, `nlon`. Regular in latitude and longitude, node-registered, stored row by row from south to north, each row from west to east |
| `levels` | one entry per probability level (a scenario has one). Each has `id`, `label`, and `measures` |
| `measures` | arrays of `nlat * nlon` integers, named `SA1P0`, `SA0P3`, `PGA`. `SA1P0` is required; bridge damage uses it, and `SA0P3` where available |
| `source` | where the values came from: `title`, `publisher`, `url`, `doi`, `version`, `retrieved_utc`, and for a scenario the event, the method and the people responsible |

Spectral accelerations are 5% damped.

## Submitting a layer

1. Convert your ground motions to the format above with **SR-HazardMaker**
   (<https://github.com/TRG-UCLA/SR-HazardMaker>). Use it in a browser, on the ShakeReady site at
   `/hazardmaker/` or on its own page, or from the command line. It reads USGS hazard-model files, USGS
   ShakeMap `grid.xml` files and plain tables of points on a regular grid, asks for the layer's source,
   checks the result, and gives you the layer file and its index entry.
2. Run `sr-hazardmaker check <your-file>.json`. It checks the structure, units and coverage, and prints
   the checksum. (The browser page runs the same checks.)
3. Add an entry for the layer to `index.json` (id, title, kind, file, site condition, levels, source,
   checksum). SR-HazardMaker writes this entry for you.
4. Open a pull request on the ShakeReady repository with the file and the index entry, or send both to
   the maintainers. Say how the ground motions were produced: the earthquake, the method or model, the site
   condition, and who to contact.
5. A maintainer reviews it, runs `python3 tools/build_provenance.py` so the layer enters the provenance
   record, and merges. The layer then appears in the map's menu.

A layer without a stated source is not accepted. Everything the map computes from a layer cites it.
