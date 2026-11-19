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
- `data/registry.json` — the inventories and fragility sets the map offers; edit it to add or remove an inventory
- `hazardmaker/` — the site's page for SR-HazardMaker. The tool itself lives in <https://github.com/TRG-UCLA/SR-HazardMaker>; `hazardmaker/lib/` and `tools/vendor/sr_hazardmaker/` are an unchanged copy of a tagged release (see `hazardmaker/lib/VERSION.json`). Do not edit the copies: change the tool, release it, and run `tools/sync_hazardmaker.py`
- `hazards/` — the hazard-layer repository: `index.json`, one file per layer, and a README with the format and how to submit
- `tools/sync_hazardmaker.py` — copies a release of SR-HazardMaker into this site
- `tools/damage_reference.py` — independent reference calculation of the bridge damage table
- `tools/build_provenance.py` and `tools/provenance_sources.json` — write the provenance record; rerun after rebuilding any data file
- `tools/build_hero.py` — draws the home-page hero artwork into `index.html` (needs numpy, scipy, contourpy)
- `data/nbi_bridges.csv` — all 25,975 bridge records as a labeled, spreadsheet-friendly table
- `data/bridges.json` — 25,974 California bridges from the FHWA National Bridge Inventory (2025), compact row format
- `data/instrumented_buildings.geojson` — 55 CESMD instrumented buildings
- `data/instrumented_nonductile_buildings.geojson` — 6 instrumented non-ductile buildings
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

## Local development

Browsers block `fetch()` from `file://` pages, so serve the folder:

    python3 -m http.server 8000

then open http://localhost:8000
