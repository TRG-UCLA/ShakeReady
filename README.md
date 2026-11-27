# ShakeReady

Interactive map of California bridges and seismically instrumented buildings — https://shakeready.org

## What's here

- `index.html` — home page
- `dashboard.html` — the dashboard: the interactive map with inventories, hazard layers and damage estimates (Leaflet + OpenStreetMap, no API keys required)
- `data.html`, `projects.html`, `publications.html`, `people.html`, `code.html` — site sections
- `assets/style.css` — shared styles
- `tools/build_bridges.py` — the bridge inventory builder: builds the bridge layer from the FHWA file (made by E. Taciroglu)
- `tools/hazus_bridges.py` — HAZUS bridge fragilities: classes and fragility curves; run it to self-test and write the fragility file (made by E. Taciroglu)
- `data/fragility/hazus_highway_bridges.json` — the HAZUS fragility set, with its source and recorded decisions
- `methods.html` — methods and provenance, drawn from `data/provenance.json`
- `data/registry.json` — the inventories and fragility sets the dashboard offers, and each inventory's filters; edit it to add or remove an inventory or a filter (see "Inventories and their filters" below)
- `hazardmaker/` — the site's page for SR-HazardMaker. The tool itself lives in <https://github.com/TRG-UCLA/SR-HazardMaker>; `hazardmaker/lib/` and `tools/vendor/sr_hazardmaker/` are an unchanged copy of a tagged release (see `hazardmaker/lib/VERSION.json`). Do not edit the copies: change the tool, release it, and run `tools/sync_hazardmaker.py`
- `hazards/` — the hazard-layer repository: `index.json`, one file per layer, and a README with the format and how to submit
- `tools/sync_hazardmaker.py` — copies a release of SR-HazardMaker into this site
- `tools/damage_reference.py` — independent reference calculation of the bridge damage table
- `tools/build_csmip_buildings.py` — builds the CSMIP Instrumented Buildings inventory from the two layers as first archived (made by E. Taciroglu)
- `tools/tests/` — checks of the dashboard made in a browser: every filter against independent counts, the damage table against the reference; see its README
- `tools/build_provenance.py` and `tools/provenance_sources.json` — write the provenance record; rerun after rebuilding any data file
- `tools/build_hero.py` — draws the home-page hero artwork into `index.html` (needs numpy, scipy, contourpy)
- `data/nbi_bridges.csv` — all 25,975 bridge records as a labeled, spreadsheet-friendly table
- `data/bridges.json` — 25,974 California bridges from the FHWA National Bridge Inventory (2025), compact row format
- `data/csmip_instrumented_buildings.geojson` — 61 CSMIP instrumented buildings, the inventory the dashboard shows; generated, not hand-edited
- `data/instrumented_buildings.geojson` (55) and `data/instrumented_nonductile_buildings.geojson` (6) — the two layers as first archived, kept unchanged; the file above is built from them
- `data/latimes_concrete_buildings.geojson` — 1,451 buildings from the LA Times concrete-building survey
- `CNAME` — binds GitHub Pages to shakeready.org

## Data notes

- One NBI record has no usable coordinates; it is in the CSV but not on the map.
- `bridges.json` format: `fields` lists the column order of each entry in `rows`.
  `kind_i` / `type_i` / `appr_kind_i` / `appr_type_i` index into `kinds` / `types`, and
  `county_i` into `counties`. `year_recon = 0` means never reconstructed. Condition ratings
  (`deck`, `superstructure`, `substructure`, `channel`, `culvert`) are 0 to 9, with -1 where the
  component does not apply. `cond` is the overall condition: Good, Fair or Poor.
  `skew` is the NBI skew angle in degrees (99 means it varies along the bridge), and `hazus` is the
  HAZUS highway bridge class number, 1 to 28.
- To rebuild the bridge layer, download the California delimited file from the FHWA NBI
  (https://www.fhwa.dot.gov/bridge/nbi/ascii.cfm) and run, from the repository root:

      python3 tools/build_bridges.py CA25.txt

  2025 is the last year FHWA published in this format; later data uses the newer SNBI
  specification and will need a revised script.

## Inventories and their filters

`data/registry.json` lists the inventories the dashboard offers. Each has an `id`, a `title`, a `format` (`nbi-rows`
for the bridge file, `geojson-points` for a GeoJSON file of points), its `file`, a `color`, whether it is `visible`
at the start, the `unit` it is counted in (singular, plural), and its `filters`. The dashboard draws and applies the
filters from this description alone. **To give an inventory a filter, add a line to the registry; no code is needed.**

Every filter has a `type`, a `label` and the `field` it reads: an attribute of a GeoJSON feature, or a column of the
bridge file. An `id` names its controls. An optional `note` is shown beneath it; in a note, `{missing}` stands for
the number of records with no value, and the note is dropped when there are none.

| `type` | What it offers | What can be set |
|---|---|---|
| `range` | A lowest and a highest number. A record with no value is left out once either end is set | `words` (the two hints; "min" and "max" if absent), `min`, `max`, `step`; `missing`: `"zero"` or `"negative"` where such a value means none |
| `select` | One choice from a list: the distinct values of the field unless said otherwise | `any` (the wording of no choice); `options` (the values, in the order to show them); `table` (the field is an index into this list in the file, such as `counties`); `order`: `name` or `count`; `counts`: true to show how many; `show`: the wording of a choice, using `{name}`, `{count}` and `{description}`; `describe_field` (the attribute that holds the description); `none` (a choice for records with no value) |
| `select` with `cases` | One of several named cases, each a test on the field's text | each case has a `label` and one of `contains`, `lacks`, or `present` (true or false) |
| `checks` | Any of several boxes. With none ticked the filter is off | `options` (values, or pairs of `value` and `label`), or `table`; `omit`; `columns`; `counts` |
| `text` | Words to find. Every word typed must appear, in any order, whatever the capitals | `fields` (the attributes searched) |
| `group` | Filters that open and close together | `label`, `filters` |

One filter is special to the bridges: `"describe": "fragility-class"` with a `prefix` takes each choice's description
from the fragility set.

A `geojson-points` inventory may also describe its popup: `popup.title` (the attribute shown as the title),
`popup.rows` (a label and an attribute each, in order; a third entry is the wording of a link) and `popup.image`.
Without one, the popup lists every attribute as recorded.

Filters take effect when "Apply filters" is pressed. What is shown, counted and downloaded is the applied selection.
After changing the registry or the dashboard, run `python3 tools/tests/test_dashboard.py`.

## Local development

Browsers block `fetch()` from `file://` pages, so serve the folder:

    python3 -m http.server 8000

then open http://localhost:8000
