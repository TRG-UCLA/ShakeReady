/* SR-HazardMaker: the converters, as they run in the browser.
   Files are read on the person's own computer; nothing is uploaded.
   Each converter here has a twin in src/sr_hazardmaker/ and the two are tested to give identical layers.
   Change them together. */
"use strict";
const SRConvert = (() => {
  const H = typeof SRHazard !== "undefined" ? SRHazard : require("./sr-hazard.js");
  const {SCALE, NODATA, FORMAT, rnd, toInt} = H;
  const BOUNDS = {lat_min: 32.0, lat_max: 42.5, lon_min: -125.0, lon_max: -113.5};     // California with a margin
  const LEVEL_INFO = {475: "10% probability of exceedance in 50 years", 975: "5% probability of exceedance in 50 years",
                      2475: "2% probability of exceedance in 50 years", 10000: "1% probability of exceedance in 100 years"};
  const r4 = v => rnd(v * 1e4) / 1e4;
  const nowUtc = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
  const isNum = s => { const c = String(s).trim(); return c !== "" && isFinite(Number(c)); };
  const slug = s => s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").slice(0, 60).replace(/^-+|-+$/g, "");
  const gen = what => `SR-HazardMaker ${H.VERSION}, browser (${what})`;

  /* ---------- zip archives: read the directory and single members without loading the whole file ---------- */
  async function zipEntries(file){
    const tailSize = Math.min(file.size, 65557 + 76);
    const tail = new DataView(await file.slice(file.size - tailSize).arrayBuffer());
    let eocd = -1;
    for (let i = tail.byteLength - 22; i >= 0; i--) if (tail.getUint32(i, true) === 0x06054b50){ eocd = i; break; }
    if (eocd < 0) throw new Error("This does not look like a zip archive.");
    let count = tail.getUint16(eocd + 10, true), cdSize = tail.getUint32(eocd + 12, true), cdOffset = tail.getUint32(eocd + 16, true);
    if (count === 0xFFFF || cdSize === 0xFFFFFFFF || cdOffset === 0xFFFFFFFF){            // ZIP64
      const loc = eocd - 20;
      if (loc < 0 || tail.getUint32(loc, true) !== 0x07064b50) throw new Error("The archive's index could not be read (ZIP64 locator missing).");
      const z64 = Number(tail.getBigUint64(loc + 8, true));
      const z = new DataView(await file.slice(z64, z64 + 56).arrayBuffer());
      if (z.getUint32(0, true) !== 0x06064b50) throw new Error("The archive's index could not be read (ZIP64 record missing).");
      count = Number(z.getBigUint64(32, true)); cdSize = Number(z.getBigUint64(40, true)); cdOffset = Number(z.getBigUint64(48, true));
    }
    const cd = new DataView(await file.slice(cdOffset, cdOffset + cdSize).arrayBuffer());
    const dec = new TextDecoder(), entries = [];
    let p = 0;
    for (let n = 0; n < count; n++){
      if (cd.getUint32(p, true) !== 0x02014b50) throw new Error("The archive's index is damaged.");
      const method = cd.getUint16(p + 10, true);
      let csize = cd.getUint32(p + 20, true), usize = cd.getUint32(p + 24, true), offset = cd.getUint32(p + 42, true);
      const nameLen = cd.getUint16(p + 28, true), extraLen = cd.getUint16(p + 30, true), commentLen = cd.getUint16(p + 32, true);
      const name = dec.decode(new Uint8Array(cd.buffer, cd.byteOffset + p + 46, nameLen));
      let e = p + 46 + nameLen; const eEnd = e + extraLen;
      while (e + 4 <= eEnd){
        const id = cd.getUint16(e, true), sz = cd.getUint16(e + 2, true);
        if (id === 0x0001){
          let q = e + 4;
          if (usize === 0xFFFFFFFF){ usize = Number(cd.getBigUint64(q, true)); q += 8; }
          if (csize === 0xFFFFFFFF){ csize = Number(cd.getBigUint64(q, true)); q += 8; }
          if (offset === 0xFFFFFFFF){ offset = Number(cd.getBigUint64(q, true)); q += 8; }
        }
        e += 4 + sz;
      }
      entries.push({name, method, csize, usize, offset});
      p += 46 + nameLen + extraLen + commentLen;
    }
    return entries;
  }
  async function zipText(file, entry){
    const lh = new DataView(await file.slice(entry.offset, entry.offset + 30).arrayBuffer());
    if (lh.getUint32(0, true) !== 0x04034b50) throw new Error(`"${entry.name}" could not be located in the archive.`);
    const start = entry.offset + 30 + lh.getUint16(26, true) + lh.getUint16(28, true);
    const blob = file.slice(start, start + entry.csize);
    const strip = t => t.replace(/^\uFEFF/, "");
    if (entry.method === 0) return strip(await blob.text());
    if (entry.method === 8){
      if (typeof DecompressionStream === "undefined") throw new Error("This browser cannot unpack archives. Unzip the file yourself and add the files inside it.");
      return strip(await new Response(blob.stream().pipeThrough(new DecompressionStream("deflate-raw"))).text());
    }
    throw new Error(`"${entry.name}" is packed in a way this page cannot read. Unzip the archive yourself and add the files inside it.`);
  }
  const isZip = f => /\.zip$/i.test(f.name);

  /* ---------- USGS National Seismic Hazard Model: uniform-hazard map tables ---------- */
  const NSHM_KEYS = {SA1P0: /(^|[^a-z0-9])sa1p0([^a-z0-9]|$)/i, SA0P3: /(^|[^a-z0-9])sa0p3([^a-z0-9]|$)/i, PGA: /(^|[^a-z0-9])pga([^a-z0-9]|$)/i};
  const measureFromName = name => Object.keys(NSHM_KEYS).find(k => NSHM_KEYS[k].test(name)) || null;

  /* From the files a person adds, find one table per measure. An archive may hold several site conditions. */
  async function nshmFind(files){
    const groups = {}, notes = [];
    const put = (group, measure, item) => { (groups[group] = groups[group] || {})[measure] = item; };
    for (const f of files){
      if (isZip(f)){
        const entries = await zipEntries(f);
        const maps = entries.filter(e => /(^|\/)map\.csv$/i.test(e.name));
        for (const e of maps){
          const m = measureFromName(e.name); if (!m) continue;
          const vs = (e.name.match(/vs30[-_]?(\d+)/i) || [])[1];
          put(vs ? `Vs30 = ${vs} m/s` : "from " + f.name, m, {name: `${f.name} → ${e.name}`, read: () => zipText(f, e), bytes: e.usize});
        }
        notes.push(`${f.name}: ${entries.length.toLocaleString("en-US")} files inside, ${maps.length} of them hazard-map tables.`);
      } else {
        const m = measureFromName(f.name);
        if (m) put("the files you added", m, {name: f.name, read: async () => (await f.text()).replace(/^\uFEFF/, ""), bytes: f.size});
        else notes.push(`${f.name}: the name does not say which measure it holds. Rename it to include SA1P0, SA0P3 or PGA.`);
      }
    }
    return {groups, notes};
  }

  function parseMapCsv(text, name){
    const nl = text.indexOf("\n");
    const header = text.slice(0, nl < 0 ? text.length : nl).replace(/^\uFEFF/, "").replace(/\r$/, "").split(",").map(c => c.trim());
    const low = header.map(c => c.toLowerCase());
    const ilon = low.findIndex(c => ["lon", "longitude", "long", "x"].includes(c)), ilat = low.findIndex(c => ["lat", "latitude", "y"].includes(c));
    if (ilon < 0 || ilat < 0) throw new Error(`${name}: no longitude and latitude columns. The columns are: ${header.join(", ")}.`);
    const periods = {};
    header.forEach((c, i) => { const rp = Number(c); if (c !== "" && isFinite(rp) && rp >= 50) periods[rnd(rp)] = i; });
    if (!Object.keys(periods).length) throw new Error(`${name}: no return-period columns. The columns are: ${header.join(", ")}.`);
    const out = {}; for (const rp in periods) out[rp] = new Map();
    let pos = nl + 1, rows = 0;
    const N = nl < 0 ? 0 : text.length;
    while (pos < N){
      let end = text.indexOf("\n", pos); if (end < 0) end = N;
      const line = text.slice(pos, end); pos = end + 1;
      if (line.length < 3) continue;
      const r = line.split(","), lon = Number(r[ilon]), lat = Number(r[ilat]);
      rows++;
      if (!(lat >= BOUNDS.lat_min && lat <= BOUNDS.lat_max && lon >= BOUNDS.lon_min && lon <= BOUNDS.lon_max)) continue;
      const key = r4(lat) + "," + r4(lon);
      for (const rp in periods){
        const cell = (r[periods[rp]] || "").trim();
        if (cell !== "" && cell !== "NaN" && cell !== "nan" && cell !== "null") out[rp].set(key, Number(cell));
      }
    }
    return {periods: out, header, rows};
  }

  /* Details that can be read off the file names: release, site condition, source. */
  function nshmDefaults(groupLabel, names){
    const all = names.join(" ");
    const r2 = /2023[._-]?r2/i.test(all), vs = (groupLabel.match(/Vs30 = (\d+)/) || [])[1], sc = (all.match(/-sc([A-E]{1,2})-/) || [])[1];
    return {
      id: "usgs-nshm" + (r2 ? "-2023r2" : "") + (vs ? `-vs${vs}` : ""),
      title: "USGS National Seismic Hazard Model" + (r2 ? " 2023, revision 2" : "") + (vs ? `, Vs30 ${vs} m/s` : ""),
      site_condition: vs ? `The same ground condition everywhere: Vs30 = ${vs} m/s` + (sc ? ` (site class ${sc})` : "") + ". Local soil is not accounted for" : "",
      description: "Uniform-hazard ground motions: at each place, the shaking with the stated chance of being exceeded. Not a single earthquake.",
      source: {title: r2 ? "Mean Seismic Hazard Curves and Uniform-Hazard Ground Motion Values from the Revised 2023 US 50-state National Seismic Hazard Model (CONUS.2023.R2)" : "",
               publisher: "U.S. Geological Survey", version: r2 ? "CONUS.2023.R2" : "", doi: r2 ? "10.5066/P14VGAV4" : "", url: r2 ? "https://doi.org/10.5066/P14VGAV4" : ""},
    };
  }

  async function nshmBuild(items, meta, onStep){
    const data = {};
    for (const m of ["SA1P0", "SA0P3", "PGA"]){
      if (!items[m]) continue;
      onStep && onStep(`Reading ${items[m].name} …`);
      data[m] = parseMapCsv(await items[m].read(), items[m].name);
    }
    if (!data.SA1P0) throw new Error("The Sa(1.0 s) table is missing. Damage estimates need it.");
    let periods = null;
    for (const m in data){ const ks = Object.keys(data[m].periods).map(Number); periods = periods ? periods.filter(k => ks.includes(k)) : ks; }
    periods.sort((a, b) => a - b);
    if (!periods.length) throw new Error("The tables share no return period.");
    const latSet = new Set(), lonSet = new Set();
    for (const m in data) for (const rp of periods) for (const key of data[m].periods[rp].keys()){ const c = key.split(","); latSet.add(Number(c[0])); lonSet.add(Number(c[1])); }
    if (latSet.size < 2 || lonSet.size < 2) throw new Error("No values fall inside the area around California.");
    const lats = [...latSet].sort((a, b) => a - b), lons = [...lonSet].sort((a, b) => a - b);
    const minStep = a => { let d = Infinity; for (let i = 1; i < a.length; i++) d = Math.min(d, a[i] - a[i - 1]); return r4(d); };
    const dlat = minStep(lats), dlon = minStep(lons);
    const nlat = rnd((lats[lats.length - 1] - lats[0]) / dlat) + 1, nlon = rnd((lons[lons.length - 1] - lons[0]) / dlon) + 1;
    const onGrid = (a, d) => a.every(v => Math.abs((v - a[0]) / d - rnd((v - a[0]) / d)) <= 1e-3);
    if (!onGrid(lats, dlat) || !onGrid(lons, dlon)) throw new Error("The points do not lie on a regular grid.");
    const levels = periods.map(rp => {
      const measures = {};
      for (const m in data){
        const arr = new Array(nlat * nlon).fill(NODATA);
        for (const [key, v] of data[m].periods[rp]){
          const c = key.split(",");
          arr[rnd((Number(c[0]) - lats[0]) / dlat) * nlon + rnd((Number(c[1]) - lons[0]) / dlon)] = toInt(v);
        }
        measures[m] = arr;
      }
      return {id: "rp" + rp, label: rp.toLocaleString("en-US") + "-year return period" + (LEVEL_INFO[rp] ? ` (${LEVEL_INFO[rp]})` : ""), return_period_years: rp, measures};
    });
    const ids = levels.map(l => l.id);
    const def = ids.includes(meta.default_level) ? meta.default_level : ids.includes("rp975") ? "rp975" : ids[0];
    return {
      format: FORMAT, id: meta.id, title: meta.title, kind: "probabilistic", description: meta.description || "", site_condition: meta.site_condition,
      units: "g", scale: SCALE, nodata: NODATA,
      grid: {lat_min: lats[0], lon_min: lons[0], dlat, dlon, nlat, nlon},
      default_level: def, levels,
      source: Object.assign({}, meta.source, {input_files: Object.keys(data).map(m => ({measure: m, file: items[m].name, bytes: items[m].bytes, rows: data[m].rows}))}),
      provenance: {generator: gen("USGS hazard-model files"), generated_utc: nowUtc(), cropped_to: BOUNDS, stored_precision_g: SCALE},
    };
  }

  /* ---------- USGS ShakeMap: grid.xml ---------- */
  const UNIT_TO_G = {"pctg": 0.01, "%g": 0.01, "g": 1};
  async function shakemapText(file){
    if (!isZip(file)) return {text: (await file.text()).replace(/^\uFEFF/, ""), name: file.name};
    const entries = await zipEntries(file);
    const e = entries.find(x => /(^|\/)grid\.xml$/i.test(x.name)) || entries.find(x => /grid.*\.xml$/i.test(x.name) && !/uncertainty/i.test(x.name));
    if (!e) throw new Error(`${file.name} has no grid.xml inside.`);
    return {text: await zipText(file, e), name: `${file.name} → ${e.name}`};
  }
  const unescapeXml = s => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&");
  const pairs = s => { const o = {}; s.replace(/([\w:.-]+)\s*=\s*"([^"]*)"/g, (_, k, v) => { o[k] = unescapeXml(v); return ""; }); return o; };
  const tagAttrs = (head, tag) => { const m = head.match(new RegExp("<" + tag + "(?=[\\s/>])([^>]*)>")); return m ? pairs(m[1]) : {}; };

  function shakemapParse(text, name){
    const a = text.indexOf("<grid_data>"), b = text.indexOf("</grid_data>");
    if (a < 0 || b < 0 || !/<shakemap_grid[\s>]/.test(text.slice(0, 2000))) throw new Error(`${name} is not a ShakeMap grid file. Look for the file named grid.xml among the ShakeMap's downloads.`);
    const head = text.slice(0, a);
    const top = tagAttrs(head, "shakemap_grid"), event = tagAttrs(head, "event"), spec = tagAttrs(head, "grid_specification");
    const fields = [...head.matchAll(/<grid_field(?=[\s/>])([^>]*)>/g)].map(m => pairs(m[1])).map(f => ({index: Number(f.index), name: f.name, units: (f.units || "").trim()}));
    const col = n => fields.find(f => f.name.toUpperCase() === n);
    const fLon = col("LON"), fLat = col("LAT");
    if (!fLon || !fLat || !spec.nlon) throw new Error(`${name}: the grid description is incomplete.`);
    const want = {SA1P0: col("PSA10"), SA0P3: col("PSA03"), PGA: col("PGA")};
    if (!want.SA1P0) throw new Error(`${name} has no spectral acceleration at 1.0 second (PSA10), which damage estimates need. Its fields are: ${fields.map(f => f.name).join(", ")}.`);
    const factor = {};
    for (const m in want){
      if (!want[m]){ delete want[m]; continue; }
      const u = want[m].units.toLowerCase().replace(/\s+/g, "");
      if (!(u in UNIT_TO_G)) throw new Error(`${name}: ${want[m].name} is in units of "${want[m].units}", which cannot be converted to g.`);
      factor[m] = UNIT_TO_G[u];
    }
    const nlon = Number(spec.nlon), nlat = Number(spec.nlat), lon_min = Number(spec.lon_min), lat_min = Number(spec.lat_min);
    const dlon = (Number(spec.lon_max) - lon_min) / (nlon - 1), dlat = (Number(spec.lat_max) - lat_min) / (nlat - 1);
    const measures = {}; for (const m in want) measures[m] = new Array(nlat * nlon).fill(NODATA);
    const iLon = fLon.index - 1, iLat = fLat.index - 1, cols = Object.keys(want).map(m => [m, want[m].index - 1, factor[m]]);
    let pos = a + 11, rows = 0, off = 0;
    while (pos < b){
      let end = text.indexOf("\n", pos); if (end < 0 || end > b) end = b;
      const line = text.slice(pos, end).trim(); pos = end + 1;
      if (!line) continue;
      const r = line.split(/\s+/), i = rnd((Number(r[iLon]) - lon_min) / dlon), j = rnd((Number(r[iLat]) - lat_min) / dlat);
      rows++;
      if (i < 0 || j < 0 || i >= nlon || j >= nlat){ off++; continue; }
      for (const [m, c, k] of cols){ if (r[c] !== undefined && isNum(r[c])) measures[m][j * nlon + i] = toInt(Number(r[c]) * k); }
    }
    return {top, event, spec, fields, measures, grid: {lat_min, lon_min, dlat: Number(dlat.toFixed(8)), dlon: Number(dlon.toFixed(8)), nlat, nlon}, rows, off, expected: nlat * nlon,
            units: Object.fromEntries(Object.keys(want).map(m => [m, want[m].units]))};
  }
  function shakemapDefaults(p){
    const ev = p.event, top = p.top, id = ev.event_id || top.event_id || "event";
    const day = (ev.event_timestamp || "").slice(0, 10);
    const scenario = (top.shakemap_event_type || "").toUpperCase() === "SCENARIO";
    return {
      id: `shakemap-${id.toLowerCase().replace(/[^a-z0-9._-]/g, "")}-v${top.shakemap_version || "0"}`,
      title: `M ${ev.magnitude || "?"} ${ev.event_description || id}${day ? ", " + day : ""} (USGS ShakeMap)`,
      site_condition: "Site-specific: the ShakeMap's own estimate at each place, which includes its allowance for local ground",
      description: scenario ? "A scenario earthquake computed with ShakeMap." : "A recorded earthquake: ShakeMap's estimate of the shaking, guided by instrumental records and reports where available.",
      source: {title: `USGS ShakeMap for event ${id}, version ${top.shakemap_version || "?"}`, publisher: "U.S. Geological Survey" + (top.shakemap_originator ? ` (network ${top.shakemap_originator})` : ""),
               url: `https://earthquake.usgs.gov/earthquakes/eventpage/${id}`,
               version: `ShakeMap version ${top.shakemap_version || "?"}, software ${top.code_version || "?"}, processed ${top.process_timestamp || "?"}, status ${top.map_status || "?"}`},
    };
  }
  const num = s => (s !== undefined && s !== null && isNum(s)) ? Number(s) : null;
  function shakemapBuild(p, meta, fileName){
    const ev = p.event;
    return {
      format: FORMAT, id: meta.id, title: meta.title, kind: "scenario", description: meta.description || "", site_condition: meta.site_condition,
      units: "g", scale: SCALE, nodata: NODATA, grid: p.grid, default_level: "event",
      levels: [{id: "event", label: "Event", measures: p.measures}],
      source: Object.assign({}, meta.source, {
        event: {id: ev.event_id === undefined ? null : ev.event_id, magnitude: num(ev.magnitude), depth_km: num(ev.depth), latitude: num(ev.lat), longitude: num(ev.lon),
                time: ev.event_timestamp === undefined ? null : ev.event_timestamp, description: ev.event_description === undefined ? null : ev.event_description,
                type: (p.top.shakemap_event_type || "").toUpperCase() === "SCENARIO" ? "scenario" : "recorded"},
        input_files: [{file: fileName, rows: p.rows, units_in_file: p.units}]}),
      provenance: {generator: gen("USGS ShakeMap grid"), generated_utc: nowUtc(), stored_precision_g: SCALE,
                   note: "Values converted to g from the units stated in the file. The whole ShakeMap grid is kept."},
    };
  }

  /* ---------- a table of points on a regular grid ---------- */
  const TABLE_UNITS = {"g": 1, "%g": 0.01, "cm/s²": 1 / 980.665, "m/s²": 1 / 9.80665};
  function tableRead(text){
    const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter(l => l.trim() !== "");
    if (lines.length < 5) throw new Error("The table has too few rows.");
    const delim = [",", "\t", ";"].map(d => [d, lines[0].split(d).length]).sort((a, b) => b[1] - a[1])[0][0];
    const first = lines[0].split(delim).map(c => c.trim().replace(/^"|"$/g, ""));
    const hasHeader = first.some(c => c !== "" && !isNum(c));
    const header = hasHeader ? first : first.map((_, i) => "column " + (i + 1));
    const rows = (hasHeader ? lines.slice(1) : lines).map(l => l.split(delim));
    const low = header.map(c => c.toLowerCase().replace(/[\s_()]/g, ""));
    const find = tests => low.findIndex(c => tests.some(t => typeof t === "string" ? c === t : t.test(c)));
    const guess = {
      lon: find(["lon", "longitude", "long", "x", "lng"]), lat: find(["lat", "latitude", "y"]),
      SA1P0: find(["sa1p0", "sa1.0", "sa10", "psa10", "sa1", "sa1.0s", "sa1s", /^p?sa\[?1(\.0+)?s?\]?$/]),
      SA0P3: find(["sa0p3", "sa0.3", "sa03", "psa03", "sa0.3s", /^p?sa\[?0?\.3s?\]?$/]), PGA: find(["pga"]),
    };
    return {header, rows, guess};
  }
  function tableBuild(t, map, unit, meta){
    const k = TABLE_UNITS[unit];
    if (k === undefined) throw new Error(`Unknown unit "${unit}".`);
    if (!(map.lon >= 0) || !(map.lat >= 0) || !(map.SA1P0 >= 0)) throw new Error("Choose the longitude, latitude and Sa(1.0 s) columns.");
    const pts = [];
    for (const r of t.rows){
      if (map.lon >= r.length || map.lat >= r.length || r[map.lon].trim() === "") continue;
      if (isNum(r[map.lon]) && isNum(r[map.lat])) pts.push([Number(r[map.lat]), Number(r[map.lon]), r]);
    }
    if (pts.length < 4) throw new Error("Fewer than four rows have usable coordinates.");
    const r6 = v => rnd(v * 1e6) / 1e6;
    const lats = [...new Set(pts.map(p => r6(p[0])))].sort((a, b) => a - b), lons = [...new Set(pts.map(p => r6(p[1])))].sort((a, b) => a - b);
    if (lats.length < 2 || lons.length < 2) throw new Error("The points lie on a single line, not a grid.");
    const step = a => { let d = Infinity; for (let i = 1; i < a.length; i++) d = Math.min(d, a[i] - a[i - 1]); return d; };
    const nlat = rnd((lats[lats.length - 1] - lats[0]) / step(lats)) + 1, nlon = rnd((lons[lons.length - 1] - lons[0]) / step(lons)) + 1;
    const dlat = (lats[lats.length - 1] - lats[0]) / (nlat - 1), dlon = (lons[lons.length - 1] - lons[0]) / (nlon - 1);
    const onGrid = (a, d) => a.every(v => Math.abs((v - a[0]) / d - rnd((v - a[0]) / d)) <= 0.02);
    if (!onGrid(lats, dlat) || !onGrid(lons, dlon) || nlat * nlon > 4e6)
      throw new Error("The points do not lie on a regular grid of latitude and longitude. SR-HazardMaker needs evenly spaced rows and columns; scattered points are not supported yet.");
    const measures = {};
    for (const m of ["SA1P0", "SA0P3", "PGA"]){
      const c = map[m];
      if (c === undefined || c === null || c < 0) continue;
      const arr = new Array(nlat * nlon).fill(NODATA);
      for (const [lat, lon, r] of pts){
        const cell = c < r.length ? r[c].trim() : "";
        if (cell === "" || !isNum(cell)) continue;
        arr[rnd((lat - lats[0]) / dlat) * nlon + rnd((lon - lons[0]) / dlon)] = toInt(Number(cell) * k);
      }
      measures[m] = arr;
    }
    const kind = meta.kind || "scenario";
    return {
      format: FORMAT, id: meta.id, title: meta.title, kind, description: meta.description || "", site_condition: meta.site_condition,
      units: "g", scale: SCALE, nodata: NODATA,
      grid: {lat_min: lats[0], lon_min: lons[0], dlat: Number(dlat.toFixed(8)), dlon: Number(dlon.toFixed(8)), nlat, nlon},
      default_level: "level", levels: [{id: "level", label: meta.level_label || (kind === "scenario" ? "Event" : "Hazard level"), measures}],
      source: Object.assign({}, meta.source, {input_files: [{file: meta.file_name === undefined ? null : meta.file_name, rows: t.rows.length, units_in_file: unit,
              columns: Object.fromEntries(Object.entries(map).filter(e => e[1] !== null && e[1] >= 0).map(e => [e[0], t.header[e[1]]]))}]}),
      provenance: {generator: gen("table of points"), generated_utc: nowUtc(), stored_precision_g: SCALE,
                   note: `Values converted to g from ${unit}. ${pts.length.toLocaleString("en-US")} points placed on a ${nlat} by ${nlon} grid.`},
    };
  }

  return {BOUNDS, slug, nowUtc, isZip, zipEntries, zipText, nshmFind, parseMapCsv, nshmDefaults, nshmBuild, shakemapText, shakemapParse, shakemapDefaults, shakemapBuild, tableRead, tableBuild, TABLE_UNITS};
})();
if (typeof module !== "undefined" && module.exports) module.exports = SRConvert;
