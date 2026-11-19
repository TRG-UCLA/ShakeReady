/* SPDX-License-Identifier: BSD-3-Clause
   Copyright (c) 2026, E. Taciroglu. Part of SR-HazardMaker; see LICENSE. */
/* SR-HazardMaker: the ShakeReady hazard-layer format in the browser.
   Reading a value at a site, checking and summarizing a layer, drawing it, keeping layers locally.
   This file and src/sr_hazardmaker/grid.py implement the same rules and are tested to agree. */
"use strict";
const SRHazard = (() => {
  const VERSION = "0.3.3";
  const MAKER = "E. Taciroglu", YEAR = "2026", LICENSE = "BSD-3-Clause", URL = "https://github.com/TRG-UCLA/SR-HazardMaker";
  const DOI = "10.5281/zenodo.24356049";            // for all versions; each release also has its own, listed on the Zenodo record
  const MADE_WITH = "SR-HazardMaker, made by E. Taciroglu (https://doi.org/10.5281/zenodo.24356049)";     // written into every layer
  const FORMAT = "shakeready-hazard-grid/1";
  const MEASURES = ["SA1P0", "SA0P3", "PGA"];
  const MEASURE_NAMES = {SA1P0: "Sa(1.0 s)", SA0P3: "Sa(0.3 s)", PGA: "PGA"};
  const SCALE = 0.001, NODATA = -1;
  const CALIFORNIA = {lat_min: 32.5, lat_max: 42.0, lon_min: -124.5, lon_max: -114.1};
  const SHAKE_STOPS = [[0.02, "#5B6FD6"], [0.05, "#3D7DD8"], [0.1, "#38B6C9"], [0.2, "#7BD389"], [0.4, "#F2D16B"], [0.8, "#F9A03F"], [1.5, "#F46036"], [3, "#D7263D"]];
  const rnd = x => Math.floor(x + 0.5);            // nearest integer, an exact half upward
  const toInt = g => rnd(g / SCALE);

  /* Ground motion in g at a point: bilinear between the four surrounding nodes.
     Nodes without a value are left out and the remaining weights rescaled. Null outside the grid. */
  function valueAt(h, values, lat, lng){
    const g = h.grid, x = (lng - g.lon_min) / g.dlon, y = (lat - g.lat_min) / g.dlat;
    if (x < 0 || y < 0 || x > g.nlon - 1 || y > g.nlat - 1) return null;
    const i0 = Math.min(Math.floor(x), g.nlon - 2), j0 = Math.min(Math.floor(y), g.nlat - 2), fx = x - i0, fy = y - j0;
    let total = 0, weight = 0;
    const add = (dj, di, w) => { const v = values[(j0 + dj) * g.nlon + i0 + di]; if (v !== h.nodata && w > 0){ total += w * v; weight += w; } };
    add(0, 0, (1 - fx) * (1 - fy)); add(0, 1, fx * (1 - fy)); add(1, 0, (1 - fx) * fy); add(1, 1, fx * fy);
    return weight > 0 ? total / weight * h.scale : null;
  }

  /* Range and coverage of each measure at each level. */
  function summary(h){
    const out = [];
    for (const lv of h.levels) for (const m of MEASURES){
      const arr = lv.measures[m]; if (!arr) continue;
      let min = Infinity, max = -Infinity, count = 0;
      for (let i = 0; i < arr.length; i++){ const v = arr[i]; if (v !== h.nodata){ count++; if (v < min) min = v; if (v > max) max = v; } }
      out.push({level: lv.id, label: lv.label, measure: m, count, total: arr.length, min: count ? min * h.scale : null, max: count ? max * h.scale : null});
    }
    return out;
  }

  /* Problems that make a layer unusable (errors) and things worth a second look (warnings). */
  function check(h){
    const errors = [], warnings = [];
    if (!h || h.format !== FORMAT){ errors.push(`The file's format is "${h && h.format}", not "${FORMAT}".`); return {errors, warnings}; }
    for (const k of ["id", "title", "kind", "site_condition", "units", "scale", "nodata", "grid", "levels", "source"]) if (h[k] === undefined || h[k] === "") errors.push(`"${k}" is missing.`);
    if (errors.length) return {errors, warnings};
    if (!["probabilistic", "scenario"].includes(h.kind)) errors.push(`"kind" must be probabilistic or scenario.`);
    if (h.units !== "g") errors.push(`Units must be g.`);
    if (!/^[a-z0-9][a-z0-9._-]*$/.test(h.id)) errors.push(`The identifier may use only lower-case letters, digits, dots, hyphens and underscores.`);
    const g = h.grid, n = g.nlat * g.nlon;
    if (!(g.dlat > 0 && g.dlon > 0 && g.nlat >= 2 && g.nlon >= 2)) errors.push("The grid needs positive spacing and at least 2 by 2 nodes.");
    if (!h.levels.length) errors.push("The layer has no levels.");
    for (const lv of h.levels){
      if (!lv.measures || !lv.measures.SA1P0) errors.push(`Level "${lv.id}" has no Sa(1.0 s), which damage estimates need.`);
      for (const [m, arr] of Object.entries(lv.measures || {})){
        if (!MEASURES.includes(m)) errors.push(`"${m}" is not a recognized measure.`);
        else if (arr.length !== n) errors.push(`Level "${lv.id}", ${MEASURE_NAMES[m]}: ${arr.length} values, but the grid has ${n} nodes.`);
      }
    }
    if (errors.length) return {errors, warnings};
    const latMax = g.lat_min + (g.nlat - 1) * g.dlat, lonMax = g.lon_min + (g.nlon - 1) * g.dlon;
    if (latMax < CALIFORNIA.lat_min || g.lat_min > CALIFORNIA.lat_max || lonMax < CALIFORNIA.lon_min || g.lon_min > CALIFORNIA.lon_max)
      warnings.push("The grid does not overlap California, so no structure on the ShakeReady map falls inside it.");
    const s = h.source || {};
    for (const [k, label] of [["title", "a title"], ["publisher", "a publisher or author"], ["retrieved_utc", "the date it was obtained or made"]])
      if (!s[k]) warnings.push(`The source has no ${label}. A layer cannot be published without saying where it came from.`);
    for (const row of summary(h)){
      if (row.count === 0) errors.push(`Level "${row.level}", ${MEASURE_NAMES[row.measure]}: no node has a value.`);
      else if (row.min < 0 || row.max > 10) warnings.push(`Level "${row.level}", ${MEASURE_NAMES[row.measure]}: values run from ${row.min.toFixed(3)} to ${row.max.toFixed(3)} g. Check the units.`);
    }
    return {errors, warnings};
  }

  /* How to cite the tool. src/sr_hazardmaker/__init__.py gives the same. */
  function citation(){
    const where = DOI ? "https://doi.org/" + DOI : URL;
    const lines = ["@software{taciroglu_sr_hazardmaker,", "  author  = {Taciroglu, E.},", "  title   = {{SR-HazardMaker}},", `  year    = {${YEAR}},`, `  version = {${VERSION}},`];
    if (DOI) lines.push(`  doi     = {${DOI}},`);
    lines.push(`  url     = {${URL}}`, "}");
    return {text: `Taciroglu, E. (${YEAR}). SR-HazardMaker (Version ${VERSION}) [Computer software]. ${where}`, bibtex: lines.join("\n")};
  }

  const serialize = layer => JSON.stringify(layer);
  function indexEntry(layer, sha256, bytes){
    const s = layer.source || {};
    return {id: layer.id, title: layer.title, kind: layer.kind, file: `hazards/${layer.id}.json`, site_condition: layer.site_condition, description: layer.description || "",
            measures: Object.keys(layer.levels[0].measures).sort(), levels: layer.levels.map(l => ({id: l.id, label: l.label})),
            source: Object.fromEntries(["title", "publisher", "url", "doi", "version", "retrieved_utc"].filter(k => s[k]).map(k => [k, s[k]])), sha256, bytes};
  }

  const hexRgb = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  function shakeColor(v){
    const S = SHAKE_STOPS; let i = 0;
    if (v <= S[0][0]) return hexRgb(S[0][1]);
    if (v >= S[S.length - 1][0]) return hexRgb(S[S.length - 1][1]);
    while (v > S[i + 1][0]) i++;
    const t = Math.log(v / S[i][0]) / Math.log(S[i + 1][0] / S[i][0]), a = hexRgb(S[i][1]), b = hexRgb(S[i + 1][1]);
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
  }
  /* The shaking as an image, resampled to the web-map projection so that it lines up with what is drawn on top. */
  function overlayCanvas(h, values){
    const g = h.grid, south = g.lat_min, north = g.lat_min + (g.nlat - 1) * g.dlat, west = g.lon_min, east = g.lon_min + (g.nlon - 1) * g.dlon;
    const my = lat => Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)), myN = my(north), myS = my(south);
    const W = Math.min(1100, g.nlon * 3), H = Math.max(2, Math.round(W * (myN - myS) / ((east - west) * Math.PI / 180)));
    const canvas = document.createElement("canvas"); canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext("2d"), img = ctx.createImageData(W, H);
    for (let py = 0; py < H; py++){
      const lat = (2 * Math.atan(Math.exp(myN - (py + .5) / H * (myN - myS))) - Math.PI / 2) * 180 / Math.PI;
      for (let px = 0; px < W; px++){
        const v = valueAt(h, values, lat, west + (px + .5) / W * (east - west));
        if (v === null) continue;
        const c = shakeColor(v), o = (py * W + px) * 4;
        img.data[o] = c[0]; img.data[o + 1] = c[1]; img.data[o + 2] = c[2]; img.data[o + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return {canvas, bounds: [[south, west], [north, east]]};
  }
  function legendHtml(measure){
    return `<div class="bar" style="background:linear-gradient(90deg,${SHAKE_STOPS.map(s => s[1]).join(",")})"></div>`
      + `<div class="ticks">` + SHAKE_STOPS.map(s => `<span>${s[0]}</span>`).join("") + `</div>${MEASURE_NAMES[measure]}, in g`;
  }

  /* What a layer says about the earthquake behind it, for drawing: the fault trace and surface footprint of a
     computed scenario, or the epicenter of a ShakeMap. Null if the layer says neither. */
  function sourceInfo(layer){
    const s = (layer && layer.source) || {}, out = {trace: null, footprint: null, epicenter: null};
    const pair = p => Array.isArray(p) && p.length === 2 && typeof p[0] === "number" && typeof p[1] === "number";
    if (s.scenario && Array.isArray(s.scenario.trace) && s.scenario.trace.length === 2 && s.scenario.trace.every(pair)){
      out.trace = s.scenario.trace;
      if (Array.isArray(s.scenario.surface_projection) && s.scenario.surface_projection.length === 4 && s.scenario.surface_projection.every(pair)) out.footprint = s.scenario.surface_projection;
    }
    if (s.event && typeof s.event.latitude === "number" && typeof s.event.longitude === "number") out.epicenter = [s.event.latitude, s.event.longitude];
    return out.trace || out.epicenter ? out : null;
  }
  function sourceLegend(layer){
    const i = sourceInfo(layer); if (!i) return "";
    return [i.trace ? "Red line: the fault" : "", i.footprint ? "dashed outline: the rupture's footprint at the surface" : "", i.epicenter ? "\u2605: the epicenter" : ""].filter(Boolean).join("; ") + ".";
  }
  /* Draw it with Leaflet (passed in as L). Returns a layer group to add to a map, or null. Give options.pane to place it in a map pane. */
  function drawSource(L, layer, options){
    const i = sourceInfo(layer); if (!i) return null;
    const base = Object.assign({interactive: false}, options && options.pane ? {pane: options.pane} : {}), g = L.layerGroup();
    if (i.footprint) L.polygon(i.footprint, Object.assign({color: "#D7263D", weight: 1.5, dashArray: "5 4", fillColor: "#D7263D", fillOpacity: 0.08}, base)).addTo(g);
    if (i.trace){
      L.polyline(i.trace, Object.assign({color: "#FFFFFF", weight: 7, opacity: 0.9}, base)).addTo(g);
      L.polyline(i.trace, Object.assign({color: "#D7263D", weight: 3.5}, base)).addTo(g);
    }
    if (i.epicenter) L.marker(i.epicenter, Object.assign({keyboard: false, icon: L.divIcon({className: "sr-epicenter", iconSize: [24, 24],
      html: '<span style="display:block;font-size:24px;line-height:24px;text-align:center;color:#D7263D;text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 2px #fff">\u2605</span>'})}, base)).addTo(g);
    return g;
  }

  async function sha256Hex(text){
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
  }

  /* Layers a person has made or opened and kept in this browser. They are not published. */
  const DB = "shakeready", STORE = "local-hazards";
  function open(){
    return new Promise((res, rej) => {
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(STORE, {keyPath: "id"});
      r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
    });
  }
  async function tx(mode, fn){
    const d = await open();
    return new Promise((res, rej) => {
      const t = d.transaction(STORE, mode), q = fn(t.objectStore(STORE));
      t.oncomplete = () => { d.close(); res(q && q.result); };
      t.onerror = t.onabort = () => { d.close(); rej(t.error); };
    });
  }
  const store = {
    list: () => tx("readonly", s => s.getAll()).then(rows => (rows || []).map(r => ({id: r.id, title: r.title, kind: r.kind, saved_utc: r.saved_utc, sha256: r.sha256, bytes: r.bytes}))).catch(() => []),
    get: id => tx("readonly", s => s.get(id)).catch(() => null),
    put: rec => tx("readwrite", s => s.put(rec)),
    remove: id => tx("readwrite", s => s.delete(id)),
    /* keep a layer given as the text of its file; returns the stored record */
    async putText(text){
      const layer = JSON.parse(text), c = check(layer);
      if (c.errors.length) throw new Error(c.errors.join(" "));
      const rec = {id: layer.id, title: layer.title, kind: layer.kind, saved_utc: new Date().toISOString().replace(/\.\d+Z$/, "Z"), sha256: await sha256Hex(text), bytes: new Blob([text]).size, layer};
      await store.put(rec); return rec;
    },
  };

  return {VERSION, MAKER, YEAR, LICENSE, URL, DOI, MADE_WITH, citation, FORMAT, MEASURES, MEASURE_NAMES, SCALE, NODATA, CALIFORNIA, SHAKE_STOPS, rnd, toInt, valueAt, check, summary, serialize, indexEntry, shakeColor, overlayCanvas, legendHtml, sourceInfo, sourceLegend, drawSource, sha256Hex, store};
})();
if (typeof module !== "undefined" && module.exports) module.exports = SRHazard;
