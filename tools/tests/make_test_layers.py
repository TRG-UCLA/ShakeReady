"""Made-up hazard layers, for testing only. Part of ShakeReady. Made by E. Taciroglu.

They are smooth invented surfaces, not ground motions. They are written into a temporary copy of the site by the
test run and deleted with it. Never put one in the repository's hazards/ folder.
"""
import json, math, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'vendor'))
from sr_hazardmaker import grid as G


def layer(id_, title, kind, lat0, lon0, d, nlat, nlon, levels, hole=None):
    out = {"format": G.FORMAT, "id": id_, "title": title, "kind": kind, "site_condition": "Vs30 = 760 m/s (made up, for testing)",
           "units": "g", "scale": G.SCALE, "nodata": G.NODATA,
           "grid": {"lat_min": lat0, "lon_min": lon0, "dlat": d, "dlon": d, "nlat": nlat, "nlon": nlon}, "levels": [],
           "source": {"title": "MADE-UP TEST LAYER, not real ground motions", "publisher": "ShakeReady test run", "retrieved_utc": "2026-11-26"}}
    for lid, label, amp in levels:
        m = {"SA1P0": [], "SA0P3": [], "PGA": []}
        for j in range(nlat):
            for i in range(nlon):
                lat, lon = lat0 + j * d, lon0 + i * d
                if hole and hole(lat, lon):                      # a patch with no values, to exercise "no estimate"
                    for k in m: m[k].append(G.NODATA)
                    continue
                r2 = ((lat - 34.2) / 1.6) ** 2 + ((lon + 118.4) / 2.0) ** 2
                q2 = ((lat - 37.8) / 1.2) ** 2 + ((lon + 122.2) / 1.2) ** 2
                base = amp * (0.04 + 1.1 * math.exp(-r2) + 0.8 * math.exp(-q2)) * (1 + 0.15 * math.sin(7 * lat) * math.cos(5 * lon))
                m["SA1P0"].append(G.to_int(base))
                m["SA0P3"].append(G.to_int(base * (2.1 + 0.9 * math.sin(3 * lat + lon))))
                m["PGA"].append(G.to_int(base * 0.9))
        out["levels"].append({"id": lid, "label": label, "measures": m})
    out["default_level"] = levels[0][0]
    G.validate(out)
    return out


def write(site):
    """Write a made-up hazard map (two levels, with a patch of no values) and a made-up scenario into site/hazards."""
    if os.path.exists(os.path.join(site, ".git")):
        raise SystemExit("Refusing to write made-up layers into a repository. Give a temporary copy of the site.")
    hz = os.path.join(site, "hazards")
    a = layer("test-map", "TEST hazard map (made up)", "probabilistic", 32.0, -125.0, 0.1, 106, 116,
              [("rp475", "475 years (made up)", 0.6), ("rp2475", "2,475 years (made up)", 1.3)],
              hole=lambda lat, lon: 36.0 < lat < 36.6 and -120.5 < lon < -119.6)
    b = layer("test-scenario", "TEST scenario (made up)", "scenario", 33.0, -119.6, 0.05, 61, 61, [("event", "The earthquake (made up)", 1.0)])
    entries = []
    for h in (a, b):
        with open(os.path.join(hz, h["id"] + ".json"), "w") as f: json.dump(h, f)
        entries.append({"id": h["id"], "title": h["title"], "kind": h["kind"], "file": "hazards/" + h["id"] + ".json", "site_condition": h["site_condition"],
                        "levels": [{"id": lv["id"], "label": lv["label"]} for lv in h["levels"]], "measures": list(h["levels"][0]["measures"]), "source": h["source"]})
    with open(os.path.join(hz, "index.json")) as f: idx = json.load(f)
    idx["hazards"] = entries
    with open(os.path.join(hz, "index.json"), "w") as f: json.dump(idx, f, indent=1)
