/* SPDX-License-Identifier: BSD-3-Clause
   Copyright (c) 2026, E. Taciroglu. Part of SR-ModelMaker; see LICENSE. */
/* SR-ModelMaker in the browser: the shear building template, the run package, and the results it writes.
   This file mirrors shear_building.py, runpackage.py and results.py; the model template, the run script and the
   guide come from templates.js, which is written from the Python sources. The tests require the two to agree. */
"use strict";
const SRModel = (() => {
  const T = typeof SRTemplates !== "undefined" ? SRTemplates : require("./templates.js");
  const G = 9.80665, PACKAGE_FORMAT = "shakeready-run-package/1", RESULTS_FORMAT = "shakeready-results/1";
  const DEFAULT_UNITS = {length: "m", force: "kN", mass: "t", time: "s"};
  const PER_STORY = ["peak_story_drift", "peak_story_drift_ratio", "residual_story_drift", "residual_story_drift_ratio", "peak_floor_acceleration_g"];

  /* A number written as Python writes it, so that files made here read the same as files made there. */
  function pyFloat(x){
    x = Number(x);
    if (x === 0) return "0.0";
    if (Number.isInteger(x) && Math.abs(x) < 1e16) return x.toFixed(1);
    const [mant, e] = x.toExponential().split("e"), exp = Number(e);
    if (exp < -4 || exp >= 16) return `${mant}e${exp < 0 ? "-" : "+"}${String(Math.abs(exp)).padStart(2, "0")}`;
    return String(x);
  }
  const pyList = xs => "[" + xs.map(pyFloat).join(", ") + "]";
  const pyDict = d => "{" + Object.entries(d).map(([k, v]) => `'${k}': '${v}'`).join(", ") + "}";

  function perStory(value, n, name){
    const v = (typeof value === "number" ? new Array(n).fill(value) : Array.from(value)).map(Number);
    if (v.length !== n) throw new Error(`${name} needs one value, or one per story (${n}); ${v.length} were given.`);
    return v;
  }
  function parameters(o){
    const n = Math.trunc(Number(o.stories));
    if (!(n >= 1 && n <= 100)) throw new Error("The number of stories must be between 1 and 100.");
    const p = {kind: "shear-building", name: o.name || "Shear building", stories: n, heights: perStory(o.heights, n, "Story heights"), masses: perStory(o.masses, n, "Floor masses"),
      stiffnesses: perStory(o.stiffnesses, n, "Story stiffnesses"), yield_strengths: perStory(o.yield_strengths, n, "Story yield strengths"),
      hardening: o.hardening === undefined ? 0.02 : Number(o.hardening), damping_ratio: o.damping_ratio === undefined ? 0.05 : Number(o.damping_ratio),
      p_delta: !!o.p_delta, units: Object.assign({}, o.units || DEFAULT_UNITS), g: o.g === undefined ? G : Number(o.g)};
    for (const key of ["heights", "masses", "stiffnesses", "yield_strengths"]) if (p[key].some(v => !(v > 0))) throw new Error(`Every value of ${key.replace("_", " ")} must be positive.`);
    if (!(p.hardening >= 0 && p.hardening < 1)) throw new Error("The hardening ratio must be at least 0 and less than 1.");
    if (!(p.damping_ratio >= 0 && p.damping_ratio < 1)) throw new Error("The damping ratio must be at least 0 and less than 1.");
    if (p.p_delta) for (let i = 0; i < n; i++){
      const above = p.g * p.masses.slice(i).reduce((a, b) => a + b, 0);
      if (above / p.heights[i] >= p.stiffnesses[i]) throw new Error(`With second-order effects, story ${i + 1} has no lateral stiffness left: its weight above divided by its height exceeds its stiffness.`);
    }
    return p;
  }
  function uniformStiffnessForPeriod(stories, mass, period){
    if (!(period > 0 && mass > 0)) throw new Error("The period and the mass must be positive.");
    return mass * Math.pow(2 * Math.PI / period, 2) / (4 * Math.pow(Math.sin(Math.PI / (2 * (2 * stories + 1))), 2));
  }
  function fromPeriod(o){
    const n = Math.trunc(Number(o.stories)), g = o.g === undefined ? G : Number(o.g), mass = Number(o.mass), height = Number(o.height);
    const k = uniformStiffnessForPeriod(n, mass, Number(o.period));
    const fh = []; for (let i = 0; i < n; i++) fh.push(height * (i + 1));
    const total = fh.reduce((a, h) => a + mass * h, 0), weight = g * mass * n;
    const strengths = fh.map((_, i) => o.yield_coefficient * weight * fh.slice(i).reduce((a, h) => a + mass * h, 0) / total);
    const p = parameters(Object.assign({}, o, {stories: n, heights: height, masses: mass, stiffnesses: k, yield_strengths: strengths}));
    p.defined_by = {first_period_s: Number(o.period), yield_coefficient: Number(o.yield_coefficient),
      note: "uniform stiffness chosen for the period; story strengths proportional to the story shears of a mass-times-height load pattern"};
    return p;
  }
  /* Periods of a shear building without second-order effects, for display: found here by a simple iteration, not by OpenSees. */
  function firstPeriod(p){
    const n = p.stories, k = p.stiffnesses, m = p.masses;
    let x = new Array(n).fill(0).map((_, i) => i + 1), lam = 0;
    for (let it = 0; it < 500; it++){                           // inverse iteration: solve K y = M x by the chain's flexibility
      const f = x.map((v, i) => m[i] * v), y = new Array(n).fill(0);
      let shear = f.reduce((a, b) => a + b, 0), below = 0;
      for (let i = 0; i < n; i++){ below += shear / k[i]; y[i] = below; shear -= f[i]; }
      const norm = Math.max(...y.map(Math.abs)); lam = 1 / norm * Math.max(...x.map(Math.abs)); x = y.map(v => v / norm);
    }
    const f = x.map((v, i) => m[i] * v); let num = 0, den = 0, prev = 0;
    for (let i = 0; i < n; i++){ num += k[i] * Math.pow(x[i] - prev, 2); prev = x[i]; den += f[i] * x[i]; }
    return 2 * Math.PI / Math.sqrt(num / den);
  }
  function modelSource(p){
    const n = p.stories, u = p.units;
    const fill = {NAME: p.name, STORIES: n > 1 ? `${n} stories` : "one story", UNITS_TEXT: `${u.length}, ${u.force}, ${u.mass}, ${u.time}`,
      HEIGHTS: pyList(p.heights), MASSES: pyList(p.masses), STIFFNESSES: pyList(p.stiffnesses), YIELD_STRENGTHS: pyList(p.yield_strengths),
      HARDENING: pyFloat(p.hardening), DAMPING_RATIO: pyFloat(p.damping_ratio), P_DELTA: p.p_delta ? "True" : "False", G: pyFloat(p.g), UNITS: pyDict(u)};
    let out = T.MODEL;
    for (const [k, v] of Object.entries(fill)) out = out.split("{{" + k + "}}").join(v);
    return out;
  }

  /* ---- ground motions ---- */
  const ident = text => { const s = String(text).replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, ""); if (!s) throw new Error("An identifier needs at least one letter or digit."); return s; };
  function motion(id, acc, dt, scaleFactor, source){
    const a = Array.from(acc, Number), sf = scaleFactor === undefined ? 1.0 : Number(scaleFactor);
    if (a.length < 2 || !(dt > 0) || !(sf > 0)) throw new Error("A motion needs at least two values, a positive time step and a positive scale factor.");
    if (a.some(v => !Number.isFinite(v))) throw new Error(`Motion ${id} holds a value that is not a number.`);
    return {id: ident(id), dt: Number(dt), npts: a.length, scale_factor: sf, units: "g", source: source || {}, _acc: a};
  }
  /* PEER's AT2 format, in both layouts of its fourth line; or a plain column of numbers with the time step given separately. */
  function parseAT2(text, name){
    const lines = text.replace(/\r\n?/g, "\n").split("\n"), who = name || "The file";
    if (lines.length < 5) throw new Error(`${who} is too short to be an AT2 record.`);
    const m = /NPTS\s*=\s*(\d+)\s*,\s*DT\s*=\s*([0-9.Ee+-]+)/i.exec(lines[3]) || /^\s*(\d+)\s+([0-9.Ee+-]+)\s+NPTS\s*,\s*DT/i.exec(lines[3]);
    if (!m) throw new Error(`${who}: the fourth line should give the number of points and the time step, but reads: ${lines[3].trim().slice(0, 80)}`);
    if (!/UNITS OF G/i.test(lines[2])) throw new Error(`${who}: expected acceleration in units of g, but the third line reads: ${lines[2].trim().slice(0, 80)}`);
    const acc = [];
    for (const ln of lines.slice(4)) for (const tok of ln.trim().split(/\s+/)) if (tok !== ""){ const v = Number(tok); if (!Number.isFinite(v)) throw new Error(`${who}: ${tok.slice(0, 20)} is not a number.`); acc.push(v); }
    const npts = Number(m[1]), dt = Number(m[2]);
    if (acc.length !== npts) throw new Error(`${who}: the header promises ${npts.toLocaleString("en-US")} values and the file holds ${acc.length.toLocaleString("en-US")}.`);
    return {description: lines[1].trim(), dt, npts, acc};
  }

  /* ---- the run package ---- */
  async function sha256(text){
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, "0")).join("");
  }
  async function packageFiles(modelSourceText, modelInfo, motions, id, title, analysis){
    if (!motions || !motions.length) throw new Error("A package needs at least one ground motion.");
    if (new Set(motions.map(m => m.id)).size !== motions.length) throw new Error("Each motion needs its own identifier.");
    if (!modelSourceText.includes("def build")) throw new Error("The model must define build().");
    const files = {}, listed = [];
    for (const m of motions){
      const rel = `motions/${m.id}.txt`, text = m._acc.map(v => pyFloat(v) + "\n").join("");
      files[rel] = text;
      listed.push({id: m.id, file: rel, dt: m.dt, npts: m.npts, scale_factor: m.scale_factor, units: "g", sha256: await sha256(text), source: m.source});
    }
    const manifest = {format: PACKAGE_FORMAT, id: ident(id), title, created_utc: new Date().toISOString().replace(/\.\d+Z$/, "Z"), made_with: T.MADE_WITH,
      model: Object.assign({}, modelInfo, {file: "model.py", sha256: await sha256(modelSourceText)}), motions: listed,
      analysis: Object.assign({max_step_s: 0.005, free_vibration_s: null, tolerance: 1e-8}, analysis || {}),
      outputs: ["peak_story_drift_ratio", "residual_story_drift_ratio", "peak_floor_acceleration_g", "peak_base_shear"], requires: {python: ">=3.9", openseespy: ">=3.5"}};
    files["model.py"] = modelSourceText; files["run.py"] = T.RUN_PY; files["manifest.json"] = JSON.stringify(manifest, null, 1);
    files["README.txt"] = T.README.replace("{title}", title).replace("{n}", String(listed.length)).replace("{s}", listed.length === 1 ? "" : "s").replace("{made}", T.MADE_WITH);
    return {manifest, files};
  }
  /* A zip archive of text files, stored without compression: enough for a package, and nothing to depend on. */
  function zip(files, folder){
    const enc = new TextEncoder(), table = new Uint32Array(256);
    for (let n = 0; n < 256; n++){ let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; table[n] = c >>> 0; }
    const crc = b => { let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = table[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
    const parts = [], central = []; let offset = 0;
    const u16 = v => [v & 255, (v >>> 8) & 255], u32 = v => [v & 255, (v >>> 8) & 255, (v >>> 16) & 255, (v >>> 24) & 255];
    for (const [name, text] of Object.entries(files)){
      const nm = enc.encode((folder ? folder + "/" : "") + name), data = enc.encode(text), c = crc(data);
      const common = [...u16(20), ...u16(0x0800), ...u16(0), ...u16(0), ...u16(0x21), ...u32(c), ...u32(data.length), ...u32(data.length), ...u16(nm.length), ...u16(0)];
      const local = new Uint8Array([0x50, 0x4B, 0x03, 0x04, ...common]);
      parts.push(local, nm, data);
      central.push(new Uint8Array([0x50, 0x4B, 0x01, 0x02, ...u16(20), ...common, ...u16(0), ...u16(0), ...u16(0), ...u32(0), ...u32(offset)]), nm);
      offset += local.length + nm.length + data.length;
    }
    const csize = central.reduce((a, b) => a + b.length, 0), count = Object.keys(files).length;
    const end = new Uint8Array([0x50, 0x4B, 0x05, 0x06, ...u16(0), ...u16(0), ...u16(count), ...u16(count), ...u32(csize), ...u32(offset), ...u16(0)]);
    const all = parts.concat(central, [end]), out = new Uint8Array(all.reduce((a, b) => a + b.length, 0));
    let at = 0; for (const b of all){ out.set(b, at); at += b.length; }
    return out;
  }

  /* ---- the results ---- */
  function checkResults(r){
    if (!r || typeof r !== "object" || r.format !== RESULTS_FORMAT) throw new Error(`Results must have "format": "${RESULTS_FORMAT}". This does not look like a results.json written by a run package.`);
    const n = (r.model || {}).stories;
    if (!Number.isInteger(n) || n < 1) throw new Error("The results do not say how many stories the model has.");
    if (!r.motions || !r.motions.length) throw new Error("The results hold no motions.");
    for (const m of r.motions){
      if (!["completed", "failed"].includes(m.status)) throw new Error(`Motion ${m.motion}: unknown status.`);
      for (const key of PER_STORY){
        const v = m[key];
        if (!Array.isArray(v) || v.length !== n || v.some(x => typeof x !== "number" || !(x >= 0))) throw new Error(`Motion ${m.motion}: ${key} must hold one non-negative number per story.`);
      }
    }
    return r;
  }
  function summary(r){
    const done = r.motions.filter(m => m.status === "completed"), out = {motions: r.motions.length, completed: done.length};
    const median = xs => { const s = xs.slice().sort((a, b) => a - b), k = s.length; return k % 2 ? s[(k - 1) / 2] : 0.5 * (s[k / 2 - 1] + s[k / 2]); };
    for (const key of ["peak_story_drift_ratio", "residual_story_drift_ratio", "peak_floor_acceleration_g"]){
      const n = done.length ? done[0][key].length : 0, cols = []; for (let i = 0; i < n; i++) cols.push(done.map(m => m[key][i]));
      out[key] = {median: cols.map(median), largest: cols.map(c => Math.max(...c))};
    }
    return out;
  }
  async function matches(r, manifestText, modelText){
    const p = r.package || {};
    return [p.manifest_sha256 === await sha256(manifestText), p.model_sha256 === await sha256(modelText)];
  }
  return {VERSION: T.VERSION, MADE_WITH: T.MADE_WITH, G, DEFAULT_UNITS, pyFloat, parameters, uniformStiffnessForPeriod, fromPeriod, firstPeriod, modelSource,
          motion, parseAT2, sha256, packageFiles, zip, checkResults, summary, matches};
})();
if (typeof module !== "undefined" && module.exports) module.exports = SRModel;
