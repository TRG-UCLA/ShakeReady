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
- People tiers, in order: Faculty / Senior Researchers, Postdoctoral researchers,
  Graduate students, Undergraduate students, Industry collaborators, Alumni.
- Co-founders (shown with a badge): Ertugrul Taciroglu, Aysegul Askan, Pedro Arduino.
- Ertugrul Taciroglu is listed as Professor (no longer department chair).
- Okan Ilhan and Rafet Sisman are Associate Professors.
- Wenyang Zhang (Research Associate, TACC) stays in the top tier.
- Photos are wanted for everyone on the People page.
- Visual identity: navy `#0F1A2B`, orange `#F9A03F`, Archivo typeface, seismic-trace motif.
  The home hero shows shaking intensity as bands of color, red near the fault through orange,
  yellow, green and cyan to blue (`#D7263D #F46036 #F9A03F #F2D16B #7BD389 #38B6C9 #3D7DD8 #5B6FD6`).
  This was chosen by the owner from four drafted alternatives.

## Open items

1. **Domain:** the site currently serves at https://trg-ucla.github.io/ShakeReady/ and the
   `CNAME` file was removed on purpose so that address works. When ready to go live: add a
   `CNAME` file containing `shakeready.org`, then in Squarespace DNS replace the old A records with
   185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153, and add
   CNAME `www` -> `trg-ucla.github.io`. Then enable "Enforce HTTPS" in Settings > Pages.
   Until DNS is switched, GitHub reports the custom domain as improperly configured;
   that is expected. The old WordPress server goes offline once the records change.
2. **Headshots** for the eight people in `data/people.json`.
3. **Content** for Publications, Projects (only the UC ITS bridge-repository project is
   listed), and Code; members for the remaining People tiers.
4. **Logo and hero artwork:** three logo concepts were drafted (trace monogram badge;
   wordmark with trace underline; epicenter mark), plus a hero illustration showing a
   fault rupture with radiating waves, and silhouettes of a tunnel,
   viaduct, buildings and a suspension bridge. The hero illustration is on the home
   page, in the intensity-spectrum treatment the owner chose. No logo direction has been chosen yet; the navigation uses the wordmark with trace
   underline, and the hero pairs it with the small trace badge.

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
