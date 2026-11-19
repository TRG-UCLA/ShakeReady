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
- `dashboard.html` — the dashboard, an interactive map with inventories, hazard layers and damage estimates (Leaflet + OpenStreetMap, no API keys)
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

## Names

The page that began as "the Map" is now **the Dashboard** (`dashboard.html`), renamed at the owner's request
because it holds inventories, hazard layers, damage estimates, a summary and downloads. `map.html` remains as
a redirect that keeps old links working, including `?hazard=`. In writing, "the dashboard" is the page and
"the map" is the map inside it. Older passages of this note may still say "the map" for the page.

## Testing: check what a person sees

Two faults reached the owner because tests checked the wrong thing. Sample numbers shown as input hints
looked like filled-in values, and elements marked `hidden` were still displayed because a style rule set
their `display`. The tests had checked the `hidden` mark, not visibility. When testing a page, check what
is visible on screen (Playwright `is_visible()`), walk through it as a first-time user would, and look
at a screenshot of every new form before publishing. Do not use value-like placeholders in inputs.

The dashboard's map draws lines on a canvas (`preferCanvas`), so drawn features are not page elements. To
test them, ask Leaflet what is on the map and sample the painted pixel, or look at a screenshot.

## Credit

The owner, E. Taciroglu, is to be named as the maker of ShakeReady's codes: the bridge inventory builder
(`tools/build_bridges.py`), the HAZUS bridge fragilities (`tools/hazus_bridges.py`), the damage calculation
(`tools/damage_reference.py` and the map), and SR-HazardMaker. "Made by E. Taciroglu" appears on the Code
page, in each file's header, in the records the data files carry, in downloaded damage tables, and on the
Methods page. Keep it there, and add it to any new code. The fragility values themselves remain FEMA's and
are credited to FEMA.

## Provenance: keep results traceable

The owner's rule: anyone using results from this site must be able to tell where they came from.

- `methods.html` is the public record. Its tables are drawn from `data/provenance.json` and the fragility
  file, so the page cannot drift from the data.
- `data/provenance.json` lists every published file with its source, retrieval date, processing steps and
  SHA-256 checksum, plus every recorded decision and check. `data/bridges.json` also carries its own
  provenance stamp.
- Every choice made where a source is silent or inconsistent gets an identifier (HZ-01 ... for HAZUS,
  NBI-01 ... and BLD-01 ... for the inventories), its basis, and a measured effect. HAZUS decisions live in
  `tools/hazus_bridges.py`; the others and all static facts live in `tools/provenance_sources.json`.
- **Whenever a data file is rebuilt, or a decision is added or changed, run
  `python3 tools/build_provenance.py`** and commit the result. New derived results (hazard layers,
  damage estimates) must be added to this record, and downloads of results should cite it.
- Do not put numbers into the site from memory. Take them from a cited source and check the transcription.

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
- **Built, waiting for data:** the map is driven by registries. `data/registry.json` lists inventories
  and fragility sets; `hazards/index.json` lists hazard layers (empty until the first is added). With a
  hazard layer selected, the map reads Sa(1.0 s) and Sa(0.3 s) at each bridge, computes damage-state
  probabilities, colors the bridges, shows expected counts, and offers the asset-by-asset table for
  download with its provenance in the header. `tools/damage_reference.py` is an independent
  implementation; the map's table matched it exactly for all bridges on made-up test layers.
- **SR-HazardMaker is its own tool, in its own repository:** <https://github.com/TRG-UCLA/SR-HazardMaker>.
  **Its maker is E. Taciroglu, and he asked to be named as such:** keep his name in the guide, the
  citation file, the pages, and the `made_with` field of every layer.
  (public; web page at <https://trg-ucla.github.io/SR-HazardMaker/>). The owner wants it as a GitHub tool
  that is used in this project and shared with the public. It has a browser app (`docs/`), a Python
  package and command line (`src/sr_hazardmaker`, command `sr-hazardmaker`), the format specification,
  and a test suite that requires the browser and Python converters to produce the same layers. Tests run
  automatically on every push.
  - **This site does not keep its own copy of the code.** `hazardmaker/lib/` (browser files) and
    `tools/vendor/sr_hazardmaker/` (Python) are copied from a tagged release by
    `tools/sync_hazardmaker.py`, which records the release and checksums in `hazardmaker/lib/VERSION.json`.
    `tools/build_provenance.py` refuses to run if a copied file has been edited. To change the tool:
    change it in its repository, run its tests, tag a release, sync, re-run this site's checks.
  - **How Claude uses it in a session:** clone the repository, then
    `PYTHONPATH=src python3 -m sr_hazardmaker nshm|shakemap|table|check ...` on the files the owner provides.
  - Converters: USGS hazard-model files (an archive or its `map.csv` tables), USGS ShakeMap `grid.xml`
    (units read from the file), tables of points on a regular grid. A source is required.
  - The map can use an unpublished layer two ways: kept in the browser by the site's SR-HazardMaker page,
    or opened from a file ("Use a layer file from my computer"). Both are marked as the user's own.
  - **License and citation:** the owner wants people to use it freely and cite it. License: BSD 3-Clause,
    copyright E. Taciroglu (he was asked to confirm the copyright holder against UC policy). Citation:
    `CITATION.cff`, `sr-hazardmaker cite`, a block on the page, and the guide; tests keep the version,
    citation and license consistent. **Still to do for citation:** a DOI through Zenodo. The owner must
    switch the repository on at zenodo.org (signing in with GitHub and granting access to the TRG-UCLA
    organization); the next GitHub Release then gets a DOI. Put that DOI in `__doi__`
    (`src/sr_hazardmaker/__init__.py`), `DOI` (`docs/sr-hazard.js`), `CITATION.cff` and the README, and
    release again. His ORCID iD, once given, goes in `CITATION.cff`.
  - **Scenario builder (since 0.3.0):** magnitude, style of faulting, a straight fault trace, dip and
    width, one Vs30, median or a uniform shift in standard deviations. Model: Boore, Stewart, Seyhan and
    Atkinson (2014), base model, written from the paper with coefficients taken from the OpenQuake
    engine's table and checked against all 600 rows of that engine's verification tables. The owner asked
    to keep building and was told this model was chosen to start; **he has not yet said which other models
    he wants.** Decisions SB-01 to SB-09 are on the Methods page. Ideas not yet built: more models,
    picking the fault on a map, Vs30 that varies by place, spatially correlated realizations.
  - **The fault on the map (since 0.3.3):** `SRHazard.drawSource` draws what a layer records about its
    earthquake: a scenario's fault trace, a dipping rupture's footprint, a ShakeMap's epicenter. The tool's
    preview and the ShakeReady dashboard both use it; the map has a "Show the fault" box and zooms to a scenario
    when one is selected. The earthquake form has a map for clicking the fault's two ends (since 0.3.2).
  - **DOI: 10.5281/zenodo.24356049** (all versions; confirmed by the owner). It is in the tool's citation, `CITATION.cff`,
    the guide, the page and each layer's record. Zenodo archives every new GitHub Release automatically
    and gives it a version DOI of its own; nothing needs doing per release beyond publishing the Release.
    The owner's ORCID iD has been asked for twice and not given; add it to `CITATION.cff` if he offers it.
  - The ShakeReady site and its data have no license of their own yet. **Next, as agreed: the
    scenario builder**, with models implemented from published coefficients and checked against an
    established implementation.
- **Never publish a made-up hazard layer.** Test layers are generated in a scratch copy of the site and
  thrown away. Anything in `hazards/` is public and will be taken as real.
- **To add the first real layer (USGS National Seismic Hazard Model, CONUS 2023.R2, doi:10.5066/P14VGAV4):**
  the owner downloads the site class BC archive (about 1.9 GB) and drops it on SR-HazardMaker, which reads
  the three tables it needs and produces the layer file and index entry. Add both to `hazards/`, run
  `sr-hazardmaker check`, then `tools/build_provenance.py`. The converter was tested on files of the expected shape, not yet on
  the real ones: check the column names when they arrive.
- **Open choices for the owner:** start with the reference site condition (Vs30 = 760 m/s) or go straight
  to site-specific values; which hazard level loads by default (975 years was suggested).
- **Still to build:** SR-HazardMaker's scenario builder; site amplification from a Vs30 map;
  fragility sets for the building inventories; ground-failure damage.
- Results from a probabilistic hazard map are per-site and must not be presented as the loss from one
  earthquake. The map and the download both say so.

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
