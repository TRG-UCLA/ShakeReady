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

- `index.html` — home: hero, participating-institutions banner, section grid
- `map.html` — interactive map (Leaflet + OpenStreetMap, no API keys)
- `data.html`, `projects.html`, `publications.html`, `people.html`, `code.html`
- `assets/style.css` — shared styles and design tokens
- `data/` — all content data (see below)
- `images/people/`, `images/institutions/` — photos and logos, named by slug
- `CNAME` — intentionally absent for now (see Open items); when present it binds
  GitHub Pages to shakeready.org

## Editing content (no layout code needed)

- **People:** `data/people.json`. `tiers` sets section order and titles; each person has
  `slug`, `name`, `tier`, `title`, `affiliation`, `focus`, optional `link`, optional
  `badge`. Empty tiers are hidden automatically. A photo at `images/people/<slug>.jpg`
  replaces the initials badge.
- **Institutions:** `data/institutions.json`. A logo at `images/institutions/<slug>.svg`
  (or `.png`) replaces the name tile on the home page.
- **Bridges:** `data/bridges.json` is a compact row format; `fields` gives the column
  order, and `kind_i` / `type_i` / `appr_kind_i` / `appr_type_i` index into `kinds` and
  `types`. `year_recon = 0` means never reconstructed.

## Decisions already made

- Mission line (hero): "Disseminating tools and data that contribute to quantifying and
  improving seismic resilience, worldwide."
- Footer: "An international collaboration of universities and research centers."
- People tiers, in order: Faculty / Senior Researchers, Postdoctoral researchers,
  Graduate students, Undergraduate students, Industry collaborators, Alumni.
- Co-founders (shown with a badge): Ertugrul Taciroglu, Aysegul Askan, Pedro Arduino.
- Ertugrul Taciroglu is listed as Professor (no longer department chair).
- Okan Ilhan and Rafet Sisman are Associate Professors.
- Wenyang Zhang (Research Associate, TACC) stays in the top tier.
- Photos are wanted for everyone on the People page.
- Visual identity: ink `#19242F`, amber `#E8A33D`, Archivo typeface, seismic-trace motif.

## Open items

1. **Domain:** the site currently serves at https://trg-ucla.github.io/ShakeReady/ and the
   `CNAME` file was removed on purpose so that address works. When ready to go live: add a
   `CNAME` file containing `shakeready.org`, then in Squarespace DNS replace the old A records with
   185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153, and add
   CNAME `www` -> `trg-ucla.github.io`. Then enable "Enforce HTTPS" in Settings > Pages.
   Until DNS is switched, GitHub reports the custom domain as improperly configured;
   that is expected. The old WordPress server goes offline once the records change.
2. **Headshots** for the eight people in `data/people.json`.
3. **Institution logos**, obtained from each institution's brand office and used under
   its guidelines. Do not redraw or scrape them.
4. **Confirm the institution list** (derived from the roster's affiliations).
5. **Content** for Publications, Projects (only the UC ITS bridge-repository project is
   listed), and Code; members for the remaining People tiers.
6. **Logo and hero artwork:** three logo concepts were drafted (trace monogram badge;
   wordmark with trace underline; epicenter mark), plus a hero illustration showing a
   topographic map, a fault rupture with radiating waves, and silhouettes of a tunnel,
   viaduct, buildings and a suspension bridge. No direction has been chosen yet. The site
   currently uses the wordmark with trace underline.

## Data provenance

All datasets were rescued in November 2026 from the original WordPress site before its
server was retired: 25,431 California bridge records from the FHWA National Bridge
Inventory (about a 2016 snapshot) and three building layers (55 instrumented buildings,
6 instrumented non-ductile buildings, 1,451 LA Times concrete buildings).

- 60 bridge records have no coordinates in the source. They are in `data/nbi_bridges.csv`
  but not on the map.
- The old site's search form offered span count and condition ratings, but its database
  never sent those fields to the map, so they were not recoverable. To restore them or
  refresh the data, rebuild from the current FHWA NBI California file.
- The six non-ductile buildings had no stored coordinates; their positions come from the
  latitude and longitude in their attribute tables.
- Raw originals (KMZ files, XML dump) are archived in Google Drive under
  `TRGWeb / ShakeReady / ShakeReady site data (archived)`.

## Local preview

Browsers block `fetch()` on `file://` pages, so serve the folder:

    python3 -m http.server 8000
