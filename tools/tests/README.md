# Checks of the dashboard

Part of ShakeReady. Made by E. Taciroglu.

`test_dashboard.py` opens the regional dashboard in a real browser and uses it as a person would: it opens each
inventory, sets filters, presses "Apply filters", and reads what the page says. It checks three things.

1. **Filters.** For every filter of every inventory, the number the page reports equals an independent count made
   from the data file, and the map holds that same number of structures.
2. **Damage tables.** The table the dashboard offers for download equals, row for row, the one
   `tools/damage_reference.py` computes, for all bridges and for a county-filtered selection.
3. **What a person sees.** Inventories start closed and open and close; a change not yet applied is announced and
   changes nothing; popups, the legend, the counts and the report link say what they should.

Run it after any change to `dashboard.html`, `data/registry.json` or a data file:

    python3 tools/tests/test_dashboard.py

It needs Python 3 with Playwright and its Chromium (`pip install playwright`, then `playwright install chromium`).
The page's map libraries come from a public CDN. Where that cannot be reached, fetch them once and point to the folder:

    mkdir libs && cd libs && npm pack leaflet@1.9.4 leaflet.markercluster@1.5.3 && for f in *.tgz; do tar xzf $f --one-top-level; done
    SR_TEST_LIBS=libs python3 tools/tests/test_dashboard.py

**The hazard layers used here are made up.** `make_test_layers.py` writes them into a temporary copy of the site,
which is deleted when the run ends. They never go into `hazards/`: anything there is public and taken as real.
