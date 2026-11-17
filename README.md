# ShakeReady

Interactive map of California bridges and seismically instrumented buildings — https://shakeready.org

## What's here

- `index.html` — home page
- `map.html` — the interactive map application (Leaflet + OpenStreetMap, no API keys required)
- `data.html`, `projects.html`, `publications.html`, `people.html`, `code.html` — site sections
- `assets/style.css` — shared styles
- `data/nbi_bridges.csv` — all 25,431 bridge records as a spreadsheet-friendly table
- `data/bridges.json` — 25,371 California bridges from the FHWA National Bridge Inventory (~2016 snapshot), compact row format
- `data/instrumented_buildings.geojson` — 55 CESMD instrumented buildings
- `data/instrumented_nonductile_buildings.geojson` — 6 instrumented non-ductile buildings
- `data/latimes_concrete_buildings.geojson` — 1,451 buildings from the LA Times concrete-building survey
- `CNAME` — binds GitHub Pages to shakeready.org

## Data notes

- 60 additional NBI records have no coordinates in the source data; they are preserved in the
  project archive (Google Drive: "ShakeReady site data") but excluded from the map file.
- `bridges.json` format: `fields` lists the column order of each entry in `rows`;
  `kind_i` / `type_i` / `appr_kind_i` / `appr_type_i` index into the `kinds` / `types` lookup tables.
  `year_recon = 0` means the bridge has never been reconstructed.
- To refresh bridge data, download the current California file from the FHWA NBI
  (https://www.fhwa.dot.gov/bridge/nbi.cfm) and regenerate `bridges.json`.

## Local development

Browsers block `fetch()` from `file://` pages, so serve the folder:

    python3 -m http.server 8000

then open http://localhost:8000
