# ShakeReady

Interactive map of California bridges and seismically instrumented buildings — https://shakeready.org

## What's here

- `index.html` — home page
- `map.html` — the interactive map application (Leaflet + OpenStreetMap, no API keys required)
- `data.html`, `projects.html`, `publications.html`, `people.html`, `code.html` — site sections
- `assets/style.css` — shared styles
- `tools/build_bridges.py` — builds the bridge layer from the FHWA file
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
- To rebuild the bridge layer, download the California delimited file from the FHWA NBI
  (https://www.fhwa.dot.gov/bridge/nbi/ascii.cfm) and run, from the repository root:

      python3 tools/build_bridges.py CA25.txt

  2025 is the last year FHWA published in this format; later data uses the newer SNBI
  specification and will need a revised script.

## Local development

Browsers block `fetch()` from `file://` pages, so serve the folder:

    python3 -m http.server 8000

then open http://localhost:8000
