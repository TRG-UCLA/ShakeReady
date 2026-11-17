# ShakeReady — project handoff

Read this first. It records what was built, what was decided, and what is still open,
so the work can continue from this repository alone.

## What this is

The website for shakeready.org: a static site (no build step, no server) hosted on
GitHub Pages from this repository. ShakeReady disseminates tools and data that
contribute to quantifying and improving seismic resilience worldwide. It is an
international collaboration of universities and research centers, not a single-campus
project. The structure-inventory map is the founding archive, one holding among
several (data, code, publications, people, projects).

## Layout

- `index.html` — home: hero (rupture-to-rafters scene and tagline), section grid
- `map.html` — interactive map (Leaflet + OpenStreetMap, no API keys)
- `data.html`, `projects.html`, `publications.html`, `people.html`, `code.html`
- `assets/style.css` — shared styles and design tokens
- `data/` — all content data (see below)
- `tools/build_bridges.py` — builds the bridge layer from the FHWA file
- `tools/hazus_bridges.py` — HAZUS bridge classes and fragility curves, with a self-test
- `data/fragility/` — fragility sets; currently `hazus_highway_bridges.json`
- `tools/build_hero.py` — draws the home-page hero artwork into `index.html`
- `images/people/`, `images/institutions/` — photos and logos, named by slug
- `CNAME` — intentionally absent for now (see Open items); when present it binds
  GitHub Pages to shakeready.org

## Editing content (no layout code needed)

- **People:** `data/people.json`. `tiers` sets section order and titles; each person has
  `slug`, `name`, `tier`, `title`, `affiliation`, `focus`, optional `link`, optional
  `badge`. Empty tiers are hidden automatically. A photo at `images/people/<slug>.jpg`
  replaces the initials badge.
- **Institutions:** a participating-institutions banner was built and then removed from the
  home page at the owner's request. `data/institutions.json`, the `.inst-*` styles and
  `images/institutions/` are kept so it can be restored; nothing on the site uses them now.
- **Bridges:** `data/bridges.json` is generated, not hand-edited. Rebuild it with
  `python3 tools/build_bridges.py <FHWA state file>`; the README describes the format.

## Decisions already made

- Mission line (hero): "Disseminating tools and data that contribute to quantifying and
  improving seismic resilience, worldwide."
- Footer: "An international collaboration of universities and research centers."
- Hero tagline: "From rupture to rafters." (the phrase comes from the group's own work)
- No participating-institutions banner on the home page.
- Street View on the map: a person button (click it, then a spot on the map) and an "Open Street
  View" link in every popup. Both open Google Maps in a new tab using Google's documented Maps URLs,
  which need no API key. Street View is not embedded in the page, because the map is built on
  OpenStreetMap and Google's own little man only comes with Google's map.
- People tiers, in order: Faculty & Senior Researchers, Postdoctoral researchers,
  Graduate students, Undergraduate students, Industry collaborators, Alumni.
- Co-founders (shown with a badge): Ertugrul Taciroglu, Aysegul Askan, Pedro Arduino.
- Ertugrul Taciroglu is listed as Professor (no longer department chair).
- Okan Ilhan, Rafet Sisman and Jorge De La Crempien are Associate Professors (per the owner;
  some public pages still show an older rank for Jorge).
- Wenyang Zhang (Research Associate, TACC) stays in the top tier.
- Photos are wanted for everyone on the People page.
- Visual identity: navy `#0F1A2B`, orange `#F9A03F`, Archivo typeface.
- Logo: the ShakeReady wordmark with a Ricker pulse, the wavelet (1 - 2a^2) exp(-a^2), as its mark.
  The owner asked for this. It appears beside the wordmark in the navigation, as the browser tab
  icon, as the badge on the home page, and as the divider on the map panel.
  The home hero shows shaking intensity as bands of color, red near the fault through orange,
  yellow, green and cyan to blue (`#D7263D #F46036 #F9A03F #F2D16B #7BD389 #38B6C9 #3D7DD8 #5B6FD6`).
  This was chosen by the owner from four drafted alternatives.
  The bands are contours of a simple intensity model (distance to the rupture, directivity,
  uneven slip, and site variation including a soft-soil basin), so they are deliberately
  non-circular. The fault is drawn straight with a pair of half-headed slip arrows (right-lateral),
  with no background linework, and the artwork is kept small with fine lines. The skyline has a
  tunnel, a viaduct, one high-rise cluster, a suspension bridge, and a neighborhood of
  single-family houses. All of this is at the owner's request. To change it, edit the parameters in
  `tools/build_hero.py` and run it; do not hand-edit the SVG in `index.html`.

## Open items

1. **Domain:** the site currently serves at https://trg-ucla.github.io/ShakeReady/ and the
   `CNAME` file was removed on purpose so that address works. When ready to go live: add a
   `CNAME` file containing `shakeready.org`, then in Squarespace DNS replace the old A records with
   185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153, and add
   CNAME `www` -> `trg-ucla.github.io`. Then enable "Enforce HTTPS" in Settings > Pages.
   Until DNS is switched, GitHub reports the custom domain as improperly configured;
   that is expected. The old WordPress server goes offline once the records change.
2. **Headshots** for everyone in `data/people.json`.
3. **Content** for Publications, Projects (only the UC ITS bridge-repository project is
   listed), and Code; members for the remaining People tiers.
4. **Logo and hero artwork** are decided (see Decisions). Earlier drafts, including three logo
   concepts and four artwork alternatives, were explored on a design canvas outside this repository.

## Fragilities and the planned map restructure

- **Done:** every bridge has a HAZUS highway bridge class, assigned by `tools/hazus_bridges.py` from
  FEMA's Hazus Earthquake Model Technical Manual, Hazus 6.1 (Tables 7-1, 7-2, 7-6; Equations 7-1 to 7-4).
  The tables were transcribed from the manual and checked against its text; the code reproduces the
  manual's worked example. Choices made where the manual is silent or inconsistent are listed under
  `assumptions` in the fragility file and in the script. The map shows each bridge's class and adjusted
  medians and can filter by class.
- **Limits to keep visible:** the curves are generic; the NBI does not record retrofits, so pre-1975
  California bridges are treated as unretrofitted; 3,571 records are culverts; a skew coded 99 is
  evaluated as 45 degrees (1,706 bridges).
- **Planned by the owner, not yet built:** restructure the map around three registries (inventories,
  hazards, fragilities). Inventories can be added and removed. Hazard layers are selectable, with the US
  national hazard map as default and a scenario repository that others submit computed or recorded
  events to. Where an inventory has a fragility set, the map computes expected damage per asset,
  displays it, and offers an asset-by-asset download. The HAZUS set needs Sa(1.0 s), and Sa(0.3 s) for
  the shape factor, from the hazard layer. Results from a probabilistic hazard map are per-site and
  should not be summed across assets the way scenario results can.

## Data provenance

- **Bridges:** FHWA National Bridge Inventory, California, 2025 (file `CA25.txt`, 25,975
  records), converted with `tools/build_bridges.py`. 25,974 are on the map; one record
  (37C0440) has no usable coordinates and is in `data/nbi_bridges.csv` only. 2025 is the last
  year FHWA published in the Coding Guide format; newer data follows the SNBI specification.
  This replaced a snapshot of about 2016 that had been rescued from the original WordPress
  site. The update added span counts, county, names of the facility carried and feature
  crossed, total length, and condition ratings, which the map can now filter on.
- **Buildings:** three layers rescued in November 2026 from the original WordPress site before
  its server was retired: 55 instrumented buildings, 6 instrumented non-ductile buildings, and
  1,451 LA Times concrete buildings. The six non-ductile buildings had no stored coordinates;
  their positions come from the latitude and longitude in their attribute tables.
- Raw originals (KMZ files and the old site's XML dump) are archived in Google Drive under
  `TRGWeb / ShakeReady / ShakeReady site data (archived)`.

## Local preview

Browsers block `fetch()` on `file://` pages, so serve the folder:

    python3 -m http.server 8000
