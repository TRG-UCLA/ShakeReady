/* SR-HazardMaker: the page. SRHazardMakerApp.mount(element, options) builds the tool inside an element.
   options.mapUrl   address of a ShakeReady map on the same site, for "open the map" (optional)
   Needs sr-hazard.js and converters.js; uses Leaflet for the preview if the page has loaded it. */
"use strict";
const SRHazardMakerApp = (() => {
  const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const fmt = n => Number(n).toLocaleString("en-US");
  const SOURCE_KEYS = ["title", "publisher", "version", "doi", "url", "retrieved_utc", "contact"];
  const HELP = {
    nshm: `Add the USGS archive for one site condition (a large <code>.zip</code>; only the three tables needed are read from it), or the <code>map.csv</code> files for SA1P0, SA0P3 and PGA with those names in the file names. The layer is cropped to California and its surroundings.`,
    shakemap: `Add the ShakeMap's <code>grid.xml</code>, or the <code>grid.xml.zip</code> as downloaded. On a USGS event page it is under ShakeMap, Downloads.`,
    table: `Add one CSV file. Each row is a grid point: longitude, latitude, and spectral acceleration at 1.0 second. Spectral acceleration at 0.3 second and peak ground acceleration are optional. The points must form an evenly spaced grid.`,
  };
  const MARKUP = `
  <section class="hm-step" id="step1">
    <h2><span class="num">1</span>What do you have?</h2>
    <div class="hm-cards">
      <label class="hm-card"><input type="radio" name="kind" value="nshm"><b>USGS national hazard model files</b><span>The archive for one site condition from the National Seismic Hazard Model, or the <code>map.csv</code> tables from inside it.</span></label>
      <label class="hm-card"><input type="radio" name="kind" value="shakemap"><b>A USGS ShakeMap</b><span>The <code>grid.xml</code> file of a recorded or scenario earthquake, zipped or not.</span></label>
      <label class="hm-card"><input type="radio" name="kind" value="table"><b>A table of points</b><span>A CSV file with longitude, latitude and ground motion on an evenly spaced grid, such as the output of a simulation.</span></label>
    </div>
  </section>
  <section class="hm-step" id="step2" hidden>
    <h2><span class="num">2</span>Add the file</h2>
    <p id="file-help"></p>
    <div class="hm-drop" id="drop"><input type="file" id="files" multiple aria-label="Choose files"><span>or drop files here</span></div>
    <p class="hm-status" id="status" role="status"></p>
    <div id="file-report"></div>
    <div id="choices"></div>
  </section>
  <section class="hm-step" id="step3" hidden>
    <h2><span class="num">3</span>Describe the layer</h2>
    <p>These details travel with the layer and with every result computed from it. Fields marked with a star are required.</p>
    <div class="hm-form">
      <label class="wide">Title *<input id="f-title" type="text" autocomplete="off"></label>
      <label>Identifier *<input id="f-id" type="text" autocomplete="off" spellcheck="false"><small>Lower-case letters, digits and hyphens. It becomes the file name.</small></label>
      <label>Date obtained or made *<input id="f-date" type="date"></label>
      <label class="wide">Ground condition the values assume *<input id="f-site" type="text" autocomplete="off"><small>For example "Vs30 = 760 m/s everywhere" or "site-specific, as computed".</small></label>
      <label class="wide">Notes<textarea id="f-desc" rows="2"></textarea><small>How the ground motions were produced: the earthquake, the model or method, anything a user should know.</small></label>
      <label class="wide">Source: title *<input id="f-stitle" type="text" autocomplete="off"></label>
      <label>Source: publisher or author *<input id="f-pub" type="text" autocomplete="off"></label>
      <label>Source: version<input id="f-ver" type="text" autocomplete="off"></label>
      <label>Source: DOI<input id="f-doi" type="text" autocomplete="off" spellcheck="false" placeholder="10.xxxx/xxxxx"></label>
      <label>Source: web address<input id="f-url" type="url" autocomplete="off" spellcheck="false"></label>
      <label class="wide">Contact<input id="f-contact" type="text" autocomplete="off"><small>Who to ask about this layer. Optional, and published with the layer if given.</small></label>
    </div>
    <p><button class="btn" id="build">Build the layer</button></p>
    <p class="hm-status" id="build-status" role="status"></p>
  </section>
  <section class="hm-step" id="step4" hidden>
    <h2><span class="num">4</span>Check it</h2>
    <div id="problems"></div>
    <div id="summary"></div>
    <div class="hm-preview-controls">
      <label id="pv-level-wrap">Level <select id="pv-level"></select></label>
      <label>Measure <select id="pv-measure"></select></label>
    </div>
    <div id="preview" aria-label="Preview of the shaking"></div>
    <div class="hm-legend" id="pv-legend"></div>
  </section>
  <section class="hm-step" id="step5" hidden>
    <h2><span class="num">5</span>Use it</h2>
    <p id="default-level-wrap" hidden><label>Level the map selects first <select id="f-default"></select></label></p>
    <p class="hm-actions">
      <button class="btn" id="use-map">Keep it in this browser and open the map</button>
      <button class="btn ghost" id="dl-layer">Download the layer file</button>
      <button class="btn ghost" id="dl-entry">Download the index entry</button>
    </p>
    <p id="file-facts" class="hm-facts"></p>
    <div id="use-text"></div>
  </section>
  <section class="hm-saved">
    <h2>Layers kept in this browser</h2>
    <div id="saved-out"><p class="hm-none">None yet.</p></div>
  </section>`;

  function mount(root, options){
    const opt = options || {};
    const mapUrl = opt.mapUrl ? new URL(opt.mapUrl, location.href) : null;
    const canOpenMap = !!(mapUrl && mapUrl.origin === location.origin);          // kept layers are only visible to pages of the same site
    root.classList.add("srhm"); root.innerHTML = MARKUP;
    const $ = id => root.querySelector("#" + id);
    const S = {kind: null, files: [], nshm: null, group: null, sm: null, table: null, layer: null, text: null, sha: null, idEdited: false};
    SRHazardMakerApp.state = S;
    const status = (msg, bad) => { $("status").textContent = msg || ""; $("status").classList.toggle("bad", !!bad); };
    const mapLink = id => { const u = new URL(mapUrl); u.searchParams.set("hazard", "local:" + id); return u.href; };
    function setForm(v){
      for (const [id, val] of Object.entries(v)) if (val !== undefined) $(id).value = val;
      if (v["f-id"] !== undefined) S.idEdited = false;
      else if (!S.idEdited && v["f-title"]) $("f-id").value = SRConvert.slug(v["f-title"]);
    }
    function resetFrom(step){ for (let i = step; i <= 5; i++) $("step" + i).hidden = true; S.layer = S.text = S.sha = null; }

    $("use-map").hidden = !canOpenMap;
    $("use-text").innerHTML = (canOpenMap
      ? `<p><b>Keeping it in this browser</b> lets you use the layer on the ShakeReady map straight away, on this computer only. It is marked as yours and unpublished, and any damage table you download says so.</p>`
      : `<p><b>To use it on the ShakeReady map</b> straight away, download the layer file, open the map, and under Hazard layer choose “Use a layer file from my computer”. It stays on your computer, marked as yours and unpublished.</p>`)
      + `<p><b>To publish it</b> for everyone, send the two downloaded files to the ShakeReady maintainers, or open a pull request that adds them to the <a href="https://github.com/TRG-UCLA/ShakeReady/tree/main/hazards" rel="noopener">ShakeReady hazard repository</a>. A layer is reviewed before it is listed.</p>`;

    root.querySelectorAll('input[name="kind"]').forEach(r => r.addEventListener("change", () => {
      S.kind = r.value; S.files = []; S.nshm = S.sm = S.table = S.group = null; S.idEdited = false;
      resetFrom(3); $("step2").hidden = false;
      $("file-help").innerHTML = HELP[S.kind]; $("file-report").innerHTML = ""; $("choices").innerHTML = ""; status("");
      $("files").value = ""; $("files").multiple = S.kind === "nshm";
      ["f-title","f-id","f-site","f-desc","f-stitle","f-pub","f-ver","f-doi","f-url","f-contact"].forEach(id => $(id).value = "");
      $("f-date").value = new Date().toISOString().slice(0, 10);
    }));
    $("f-id").addEventListener("input", () => S.idEdited = true);
    $("f-title").addEventListener("input", () => { if (!S.idEdited) $("f-id").value = SRConvert.slug($("f-title").value); });

    const drop = $("drop");
    ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", e => handleFiles([...e.dataTransfer.files]));
    $("files").addEventListener("change", e => handleFiles([...e.target.files]));

    async function handleFiles(files){
      if (!files.length || !S.kind) return;
      resetFrom(3); $("file-report").innerHTML = ""; $("choices").innerHTML = "";
      status("Reading …");
      try {
        if (S.kind === "nshm") await addNshm(files);
        else if (S.kind === "shakemap") await addShakemap(files[0]);
        else await addTable(files[0]);
      } catch (err){ status(err.message || String(err), true); }
    }

    /* ----- USGS hazard model ----- */
    async function addNshm(files){
      S.files = S.files.length && files.length && !files.some(SRConvert.isZip) && !S.files.some(SRConvert.isZip) ? S.files.concat(files) : (files.length ? files : S.files);   // tables can be added one at a time
      const found = await SRConvert.nshmFind(S.files);
      S.nshm = found;
      const names = Object.keys(found.groups).filter(g => found.groups[g].SA1P0);
      let html = found.notes.map(n => `<p class="hm-note">${esc(n)}</p>`).join("");
      if (!names.length){
        const partial = Object.keys(found.groups);
        $("file-report").innerHTML = html + (partial.length ? `<p class="hm-note">Found so far: ${partial.map(g => Object.keys(found.groups[g]).join(", ")).join("; ")}. The Sa(1.0 s) table (SA1P0) is still needed.</p>` : "");
        status(partial.length ? "Add the SA1P0 table to continue." : "No hazard-map tables were found in what you added.", true); return;
      }
      if (!S.group || !names.includes(S.group)) S.group = names[0];
      const pick = names.length > 1 ? `<p><label>Site condition to use <select id="nshm-group">${names.map(g => `<option${g === S.group ? " selected" : ""}>${esc(g)}</option>`).join("")}</select></label></p>` : "";
      const g = found.groups[S.group];
      html += pick + `<table class="t"><tr><th>Measure</th><th>Table</th></tr>` + ["SA1P0", "SA0P3", "PGA"].map(m =>
        `<tr><td>${SRHazard.MEASURE_NAMES[m]}</td><td>${g[m] ? esc(g[m].name) + ` (${(g[m].bytes / 1e6).toFixed(1)} MB)` : `<span class="hm-missing">not found${m === "SA0P3" ? ": without it the spectral-shape adjustment is skipped" : ": optional"}</span>`}</td></tr>`).join("") + `</table>`;
      $("file-report").innerHTML = html;
      if ($("nshm-group")) $("nshm-group").addEventListener("change", e => { S.group = e.target.value; addNshm([]).catch(err => status(err.message, true)); });
      const d = SRConvert.nshmDefaults(S.group, S.files.map(f => f.name).concat(Object.values(g).map(x => x.name)));
      setForm({"f-title": d.title, "f-id": d.id, "f-site": d.site_condition, "f-desc": d.description, "f-stitle": d.source.title, "f-pub": d.source.publisher, "f-ver": d.source.version, "f-doi": d.source.doi, "f-url": d.source.url});
      status(""); $("step3").hidden = false;
    }

    /* ----- ShakeMap ----- */
    async function addShakemap(file){
      const {text, name} = await SRConvert.shakemapText(file);
      status("Reading the grid …"); await new Promise(r => setTimeout(r, 30));
      const p = SRConvert.shakemapParse(text, name);
      S.sm = {parsed: p, name};
      const ev = p.event, filled = p.measures.SA1P0.reduce((n, v) => n + (v !== SRHazard.NODATA), 0);
      $("file-report").innerHTML = `<table class="t">
        <tr><td>Event</td><td>M ${esc(ev.magnitude)} ${esc(ev.event_description || "")}, ${esc(ev.event_timestamp || "")} (${esc(ev.event_id || "")})</td></tr>
        <tr><td>Kind</td><td>${(p.top.shakemap_event_type || "").toUpperCase() === "SCENARIO" ? "Scenario earthquake" : "Recorded earthquake"}, ShakeMap version ${esc(p.top.shakemap_version || "?")}, status ${esc(p.top.map_status || "?")}</td></tr>
        <tr><td>Grid</td><td>${fmt(p.grid.nlon)} by ${fmt(p.grid.nlat)} points, spacing ${p.grid.dlon.toFixed(4)}° by ${p.grid.dlat.toFixed(4)}°</td></tr>
        <tr><td>Measures used</td><td>${Object.keys(p.measures).map(m => `${SRHazard.MEASURE_NAMES[m]} (given in ${esc(p.units[m])})`).join(", ")}</td></tr>
        <tr><td>Rows read</td><td>${fmt(p.rows)}; ${fmt(filled)} of ${fmt(p.expected)} grid points filled${p.off ? `; ${fmt(p.off)} rows fell outside the stated grid` : ""}</td></tr></table>`
        + (filled < p.expected ? `<p class="hm-note warn">The file fills ${fmt(filled)} of the ${fmt(p.expected)} points its header describes. The rest are left without a value.</p>` : "");
      const d = SRConvert.shakemapDefaults(p);
      setForm({"f-title": d.title, "f-id": d.id, "f-site": d.site_condition, "f-desc": d.description, "f-stitle": d.source.title, "f-pub": d.source.publisher, "f-ver": d.source.version, "f-url": d.source.url, "f-doi": ""});
      status(""); $("step3").hidden = false;
    }

    /* ----- table of points ----- */
    async function addTable(file){
      const t = SRConvert.tableRead(await file.text());
      S.table = {t, name: file.name};
      const opts = sel => `<option value="-1">not in the file</option>` + t.header.map((h, i) => `<option value="${i}"${i === sel ? " selected" : ""}>${esc(h)}</option>`).join("");
      $("file-report").innerHTML = `<p class="hm-note">${esc(file.name)}: ${fmt(t.rows.length)} rows, ${t.header.length} columns.</p>`;
      $("choices").innerHTML = `<div class="hm-form">
        <label>Longitude column *<select id="c-lon">${opts(t.guess.lon)}</select></label>
        <label>Latitude column *<select id="c-lat">${opts(t.guess.lat)}</select></label>
        <label>Sa(1.0 s) column *<select id="c-SA1P0">${opts(t.guess.SA1P0)}</select></label>
        <label>Sa(0.3 s) column<select id="c-SA0P3">${opts(t.guess.SA0P3)}</select></label>
        <label>PGA column<select id="c-PGA">${opts(t.guess.PGA)}</select></label>
        <label>Units of the ground motions *<select id="c-unit">${Object.keys(SRConvert.TABLE_UNITS).map(u => `<option>${u}</option>`).join("")}</select></label>
        <label>What the table describes *<select id="c-kind"><option value="scenario">One earthquake (a scenario or a recorded event)</option><option value="probabilistic">A hazard map at one probability level</option></select></label>
        <label>Name of the level<input id="c-level" type="text" placeholder="e.g. 975-year return period"><small>Only for a hazard map.</small></label>
      </div>`;
      status(""); $("step3").hidden = false;
    }

    /* ----- build ----- */
    function readMeta(){
      const need = [["f-title", "a title"], ["f-id", "an identifier"], ["f-site", "the ground condition"], ["f-stitle", "the source's title"], ["f-pub", "the source's publisher or author"], ["f-date", "the date"]];
      const missing = need.filter(([id]) => !$(id).value.trim()).map(x => x[1]);
      if (missing.length) throw new Error("Please give " + missing.join(", ") + ".");
      const all = {title: $("f-stitle").value.trim(), publisher: $("f-pub").value.trim(), version: $("f-ver").value.trim(), doi: $("f-doi").value.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, ""),
                   url: $("f-url").value.trim(), retrieved_utc: $("f-date").value, contact: $("f-contact").value.trim()};
      const source = {}; for (const k of SOURCE_KEYS) if (all[k]) source[k] = all[k];
      return {id: $("f-id").value.trim(), title: $("f-title").value.trim(), site_condition: $("f-site").value.trim(), description: $("f-desc").value.trim(), source};
    }
    $("build").addEventListener("click", async () => {
      const bs = $("build-status"); bs.classList.remove("bad"); resetFrom(4);
      try {
        const meta = readMeta();
        bs.textContent = "Building …"; await new Promise(r => setTimeout(r, 30));
        if (S.kind === "nshm") S.layer = await SRConvert.nshmBuild(S.nshm.groups[S.group], meta, msg => { bs.textContent = msg; });
        else if (S.kind === "shakemap") S.layer = SRConvert.shakemapBuild(S.sm.parsed, meta, S.sm.name);
        else {
          const map = {}; for (const k of ["lon", "lat", "SA1P0", "SA0P3", "PGA"]) map[k] = Number($("c-" + k).value);
          S.layer = SRConvert.tableBuild(S.table.t, map, $("c-unit").value, Object.assign(meta, {kind: $("c-kind").value, level_label: $("c-level").value.trim(), file_name: S.table.name}));
        }
        await finish();
        bs.textContent = "";
      } catch (err){ bs.textContent = err.message || String(err); bs.classList.add("bad"); }
    });

    let pvMap = null, pvOverlay = null;
    async function finish(){
      S.text = SRHazard.serialize(S.layer); S.sha = await SRHazard.sha256Hex(S.text);
      const L0 = S.layer, g = L0.grid, chk = SRHazard.check(L0);
      $("problems").innerHTML = (chk.errors.length ? `<div class="hm-problems bad"><b>This layer cannot be used yet:</b><ul>${chk.errors.map(e => `<li>${esc(e)}</li>`).join("")}</ul></div>` : "")
        + (chk.warnings.length ? `<div class="hm-problems warn"><b>Worth a second look:</b><ul>${chk.warnings.map(e => `<li>${esc(e)}</li>`).join("")}</ul></div>` : "")
        + (!chk.errors.length && !chk.warnings.length ? `<div class="hm-problems ok">No problems found.</div>` : "");
      const latMax = g.lat_min + (g.nlat - 1) * g.dlat, lonMax = g.lon_min + (g.nlon - 1) * g.dlon;
      $("summary").innerHTML = `<p>${L0.kind === "probabilistic" ? "Hazard map" : "One earthquake"}. Grid of ${fmt(g.nlat)} by ${fmt(g.nlon)} points, spacing ${g.dlat}° by ${g.dlon}°, from ${g.lat_min.toFixed(3)}° to ${latMax.toFixed(3)}° north and ${g.lon_min.toFixed(3)}° to ${lonMax.toFixed(3)}° east.</p>`
        + `<div class="hm-scroll"><table class="t"><tr><th>Level</th><th>Measure</th><th>Lowest, g</th><th>Highest, g</th><th>Points with a value</th></tr>`
        + SRHazard.summary(L0).map(r => `<tr><td>${esc(r.label)}</td><td>${SRHazard.MEASURE_NAMES[r.measure]}</td><td>${r.count ? r.min.toFixed(3) : ""}</td><td>${r.count ? r.max.toFixed(3) : ""}</td><td>${fmt(r.count)} of ${fmt(r.total)}</td></tr>`).join("") + `</table></div>`;
      $("pv-level").innerHTML = L0.levels.map(l => `<option value="${esc(l.id)}"${l.id === L0.default_level ? " selected" : ""}>${esc(l.label)}</option>`).join("");
      $("pv-level-wrap").hidden = L0.levels.length < 2;
      $("pv-measure").innerHTML = SRHazard.MEASURES.filter(m => L0.levels[0].measures[m]).map(m => `<option value="${m}">${SRHazard.MEASURE_NAMES[m]}</option>`).join("");
      $("f-default").innerHTML = $("pv-level").innerHTML; $("default-level-wrap").hidden = L0.levels.length < 2;
      $("step4").hidden = false; $("step5").hidden = false;
      ["use-map", "dl-layer", "dl-entry"].forEach(id => $(id).disabled = chk.errors.length > 0);
      showFacts(); drawPreview(true);
    }
    function showFacts(){ $("file-facts").innerHTML = `File <code>${esc(S.layer.id)}.json</code>, ${(new Blob([S.text]).size / 1e6).toFixed(2)} MB. Checksum (SHA-256): <code>${S.sha}</code>`; }
    function drawPreview(fit){
      if (!S.layer || !window.L) return;
      if (!pvMap){
        pvMap = L.map($("preview"), {scrollWheelZoom: false});
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom: 12, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(pvMap);
      }
      pvMap.invalidateSize();
      const lv = S.layer.levels.find(l => l.id === $("pv-level").value) || S.layer.levels[0], m = $("pv-measure").value;
      const o = SRHazard.overlayCanvas(S.layer, lv.measures[m]);
      if (pvOverlay) pvMap.removeLayer(pvOverlay);
      pvOverlay = L.imageOverlay(o.canvas.toDataURL(), o.bounds, {opacity: .6}).addTo(pvMap);
      if (fit) pvMap.fitBounds(o.bounds);
      $("pv-legend").innerHTML = SRHazard.legendHtml(m);
    }
    $("pv-level").addEventListener("change", () => drawPreview(false));
    $("pv-measure").addEventListener("change", () => drawPreview(false));
    $("f-default").addEventListener("change", async e => { S.layer.default_level = e.target.value; S.text = SRHazard.serialize(S.layer); S.sha = await SRHazard.sha256Hex(S.text); showFacts(); });

    /* ----- use ----- */
    function download(name, text, type){
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], {type})); a.download = name;
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    }
    $("dl-layer").addEventListener("click", () => download(S.layer.id + ".json", S.text, "application/json"));
    $("dl-entry").addEventListener("click", () => download(S.layer.id + ".index-entry.json", JSON.stringify(SRHazard.indexEntry(S.layer, S.sha, new Blob([S.text]).size), null, 1) + "\n", "application/json"));
    $("use-map").addEventListener("click", async () => {
      try {
        await SRHazard.store.put({id: S.layer.id, title: S.layer.title, kind: S.layer.kind, saved_utc: SRConvert.nowUtc(), sha256: S.sha, bytes: new Blob([S.text]).size, layer: S.layer});
        location.href = mapLink(S.layer.id);
      } catch (err){ $("file-facts").innerHTML += `<br><span class="hm-missing">This browser would not store the layer (${esc(err && err.message || err)}). Download the file instead.</span>`; }
    });
    async function listSaved(){
      const rows = await SRHazard.store.list();
      $("saved-out").innerHTML = !rows.length ? `<p class="hm-none">None yet.</p>`
        : `<div class="hm-scroll"><table class="t"><tr><th>Layer</th><th>Kind</th><th>Kept</th><th>Size</th><th></th></tr>` + rows.map(r =>
          `<tr><td>${esc(r.title)}<br><small>${esc(r.id)}</small></td><td>${r.kind === "probabilistic" ? "Hazard map" : "One earthquake"}</td><td>${esc((r.saved_utc || "").slice(0, 10))}</td><td>${((r.bytes || 0) / 1e6).toFixed(2)} MB</td>`
          + `<td>${canOpenMap ? `<a class="btn ghost small" href="${esc(mapLink(r.id))}">Open on the map</a> ` : ""}<button class="btn ghost small" data-remove="${esc(r.id)}">Remove</button></td></tr>`).join("") + `</table></div>`;
      $("saved-out").querySelectorAll("[data-remove]").forEach(b => b.addEventListener("click", async () => { await SRHazard.store.remove(b.dataset.remove); listSaved(); }));
    }
    listSaved();
    return {state: S};
  }
  return {mount, state: null};
})();
