/* SPDX-License-Identifier: BSD-3-Clause
   Copyright (c) 2026, E. Taciroglu. Part of SR-HazardMaker; see LICENSE. */
/* SR-HazardMaker: the scenario builder, as it runs in the browser.
   The ground-motion model is Boore, Stewart, Seyhan and Atkinson (2014): see src/sr_hazardmaker/bssa14.py
   for the reference and for where the coefficients come from. This file mirrors bssa14.py and scenario.py,
   and the tests require the two to give the same layer. Change them together. */
"use strict";
const SRScenario = (() => {
  const H = typeof SRHazard !== "undefined" ? SRHazard : require("./sr-hazard.js");
  const {SCALE, NODATA, FORMAT, rnd, toInt} = H;
  const NAME = "Boore, Stewart, Seyhan and Atkinson (2014)";
  const CITATION = "Boore, D. M., Stewart, J. P., Seyhan, E., and Atkinson, G. M. (2014). NGA-West2 equations for predicting PGA, PGV, and 5% damped PSA for shallow crustal earthquakes. Earthquake Spectra, 30(3), 1057-1085.";
  const MREF = 4.5, RREF = 1.0, VREF = 760.0, F1 = 0.0, F3 = 0.1, V1 = 225.0, V2 = 300.0;
  const MECHANISMS = {"unspecified": "e0", "strike-slip": "e1", "normal": "e2", "reverse": "e3"};
  const LIMITS = {magnitude: [3.0, 8.5], magnitude_normal: [3.0, 7.0], rjb_km: [0.0, 400.0], vs30: [150.0, 1500.0]};
  const COEFFS = {
    PGA: {e0: 0.4473, e1: 0.4856, e2: 0.2459, e3: 0.4539, e4: 1.431, e5: 0.05053, e6: -0.1662, Mh: 5.5, c1: -1.134, c2: 0.1917, c3: -0.008088, h: 4.5, Dc3: 0.0, c: -0.6, Vc: 1500.0, f4: -0.15, f5: -0.00701, R1: 110.0, R2: 270.0, DfR: 0.1, DfV: 0.07, phi1: 0.695, phi2: 0.495, tau1: 0.398, tau2: 0.348},
    SA0P3: {e0: 1.2217, e1: 1.2401, e2: 1.0246, e3: 1.2653, e4: 0.95676, e5: -0.1959, e6: -0.092855, Mh: 6.14, c1: -1.0948, c2: 0.13388, c3: -0.005475, h: 4.93, Dc3: 0.0, c: -0.84165, Vc: 1308.47, f4: -0.21912, f5: -0.0067, R1: 103.15, R2: 268.59, DfR: 0.138, DfV: 0.05, phi1: 0.675, phi2: 0.561, tau1: 0.363, tau2: 0.229},
    SA1P0: {e0: 0.3932, e1: 0.4218, e2: 0.207, e3: 0.4124, e4: 1.5004, e5: -0.18983, e6: 0.17895, Mh: 6.2, c1: -1.193, c2: 0.10248, c3: -0.00121, h: 5.74, Dc3: 0.0, c: -1.05, Vc: 1109.95, f4: -0.10521, f5: -0.00844, R1: 116.39, R2: 270.0, DfR: 0.098, DfV: 0.02, phi1: 0.553, phi2: 0.625, tau1: 0.498, tau2: 0.298}
  };
  const R_EARTH_KM = 6371.0, MEASURES = ["SA1P0", "SA0P3", "PGA"], MAX_NODES = 400000;
  const DEFAULTS = {dip: 90.0, width_km: 15.0, vs30: 760.0, epsilon: 0.0, spacing: 0.02, margin_km: 100.0};

  function event(C, mag, mechanism){
    const e = C[MECHANISMS[mechanism]];
    if (mag <= C.Mh) return e + C.e4 * (mag - C.Mh) + C.e5 * (mag - C.Mh) * (mag - C.Mh);
    return e + C.e6 * (mag - C.Mh);
  }
  function path(C, mag, rjb){
    const r = Math.sqrt(rjb * rjb + C.h * C.h);
    return (C.c1 + C.c2 * (mag - MREF)) * Math.log(r / RREF) + (C.c3 + C.Dc3) * (r - RREF);
  }
  function site(C, vs30, pgaRock){
    const fLin = C.c * Math.log(Math.min(vs30, C.Vc) / VREF);
    const f2 = C.f4 * (Math.exp(C.f5 * (Math.min(vs30, 760.0) - 360.0)) - Math.exp(C.f5 * (760.0 - 360.0)));
    return fLin + F1 + f2 * Math.log((pgaRock + F3) / F3);
  }
  function lnMedian(measure, mag, mechanism, rjb, vs30){
    const Cp = COEFFS.PGA, pgaRock = Math.exp(event(Cp, mag, mechanism) + path(Cp, mag, rjb)), C = COEFFS[measure];
    return event(C, mag, mechanism) + path(C, mag, rjb) + site(C, vs30, pgaRock);
  }
  function sigma(measure, mag, rjb, vs30){
    const C = COEFFS[measure];
    let tau, phi;
    if (mag <= 4.5){ tau = C.tau1; phi = C.phi1; }
    else if (mag >= 5.5){ tau = C.tau2; phi = C.phi2; }
    else { tau = C.tau1 + (C.tau2 - C.tau1) * (mag - 4.5); phi = C.phi1 + (C.phi2 - C.phi1) * (mag - 4.5); }
    if (rjb > C.R2) phi += C.DfR;
    else if (rjb > C.R1) phi += C.DfR * (Math.log(rjb / C.R1) / Math.log(C.R2 / C.R1));
    if (vs30 <= V1) phi -= C.DfV;
    else if (vs30 < V2) phi -= C.DfV * (Math.log(V2 / vs30) / Math.log(V2 / V1));
    return Math.sqrt(phi * phi + tau * tau);
  }
  function groundMotion(measure, mag, mechanism, rjb, vs30, epsilon){
    let lnY = lnMedian(measure, mag, mechanism, rjb, vs30);
    if (epsilon) lnY += epsilon * sigma(measure, mag, rjb, vs30);
    return Math.exp(lnY);
  }
  function checkInputs(mag, mechanism, vs30){
    if (!(mechanism in MECHANISMS)) throw new Error(`Mechanism must be one of: ${Object.keys(MECHANISMS).join(", ")}.`);
    const [lo, hi] = mechanism === "normal" ? LIMITS.magnitude_normal : LIMITS.magnitude;
    if (!(mag >= lo && mag <= hi)) throw new Error(`The model applies to magnitudes ${lo.toFixed(1)} to ${hi.toFixed(1)}` + (mechanism === "normal" ? " for normal faulting" : "") + `; ${num(mag)} is outside that.`);
    if (!(vs30 >= LIMITS.vs30[0] && vs30 <= LIMITS.vs30[1])) throw new Error(`The model applies to Vs30 from ${LIMITS.vs30[0].toFixed(0)} to ${LIMITS.vs30[1].toFixed(0)} m/s; ${num(vs30)} is outside that.`);
  }

  const num = x => String(Number(x));                       // 7 -> "7", 6.5 -> "6.5"
  function checkParams(p){
    const q = Object.assign({}, DEFAULTS);
    for (const [k, v] of Object.entries(p)) if (v !== null && v !== undefined && v !== "") q[k] = v;
    for (const key of ["magnitude", "mechanism", "trace"]) if (q[key] === undefined) throw new Error(`The scenario needs a ${key}.`);
    for (const key of ["magnitude", "dip", "width_km", "vs30", "epsilon", "spacing", "margin_km"]){
      q[key] = Number(q[key]);
      if (Number.isNaN(q[key])) throw new Error(`${key} is not a number.`);
    }
    const trace = [[Number(q.trace[0][0]), Number(q.trace[0][1])], [Number(q.trace[1][0]), Number(q.trace[1][1])]];
    for (const [lat, lon] of trace) if (!(lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180)) throw new Error("Each end of the fault needs a latitude from -90 to 90 and a longitude from -180 to 180.");
    q.trace = trace;
    checkInputs(q.magnitude, q.mechanism, q.vs30);
    if (!(q.dip > 0 && q.dip <= 90)) throw new Error("The dip must be more than 0 and at most 90 degrees.");
    if (!(q.width_km > 0 && q.width_km <= 60)) throw new Error("The down-dip width must be more than 0 and at most 60 km.");
    if (!(q.epsilon >= -3 && q.epsilon <= 3)) throw new Error("Epsilon must be between -3 and 3 standard deviations.");
    if (!(q.spacing >= 0.005 && q.spacing <= 0.25)) throw new Error("The grid spacing must be between 0.005 and 0.25 degrees.");
    if (!(q.margin_km >= 10 && q.margin_km <= 250)) throw new Error("The margin around the fault must be between 10 and 250 km.");
    geometry(q);
    return q;
  }
  function geometry(p){
    const [[latA, lonA], [latB, lonB]] = p.trace;
    const lat0 = (latA + latB) / 2, lon0 = (lonA + lonB) / 2;
    const ky = R_EARTH_KM * Math.PI / 180.0, kx = ky * Math.cos(lat0 * (Math.PI / 180.0));
    const ax = (lonA - lon0) * kx, ay = (latA - lat0) * ky, bx = (lonB - lon0) * kx, by = (latB - lat0) * ky;
    const length = Math.sqrt((bx - ax) * (bx - ax) + (by - ay) * (by - ay));
    if (length < 0.1) throw new Error("The two ends of the fault are the same point.");
    const ux = (bx - ax) / length, uy = (by - ay) / length;
    const w = p.dip < 90 ? p.width_km * Math.cos(p.dip * (Math.PI / 180.0)) : 0.0;     // dips to the right of the direction from the first end to the second
    return {lat0, lon0, kx, ky, ax, ay, ux, uy, nx: uy, ny: -ux, length, w};
  }
  function rjb(g, lat, lon){
    const px = (lon - g.lon0) * g.kx - g.ax, py = (lat - g.lat0) * g.ky - g.ay;
    const s = px * g.ux + py * g.uy, t = px * g.nx + py * g.ny;
    const ds = s < 0 ? -s : (s > g.length ? s - g.length : 0.0), dt = t < 0 ? -t : (t > g.w ? t - g.w : 0.0);
    return Math.sqrt(ds * ds + dt * dt);
  }
  function gridFor(p, g){
    const sp = p.spacing;
    let corners = [[g.ax, g.ay], [g.ax + g.ux * g.length, g.ay + g.uy * g.length]];
    corners = corners.concat(corners.map(([x, y]) => [x + g.nx * g.w, y + g.ny * g.w]));
    const lats = corners.map(c => g.lat0 + c[1] / g.ky), lons = corners.map(c => g.lon0 + c[0] / g.kx);
    const j0 = Math.floor((Math.min(...lats) - p.margin_km / g.ky) / sp), j1 = Math.ceil((Math.max(...lats) + p.margin_km / g.ky) / sp);
    const i0 = Math.floor((Math.min(...lons) - p.margin_km / g.kx) / sp), i1 = Math.ceil((Math.max(...lons) + p.margin_km / g.kx) / sp);
    const nlat = j1 - j0 + 1, nlon = i1 - i0 + 1;
    if (nlat * nlon > MAX_NODES) throw new Error(`That would be a grid of ${(nlat * nlon).toLocaleString("en-US")} points. Use a coarser spacing or a smaller margin.`);
    return {lat_min: rnd(j0 * sp * 1e6) / 1e6, lon_min: rnd(i0 * sp * 1e6) / 1e6, dlat: sp, dlon: sp, nlat, nlon};
  }
  function levelLabel(epsilon){
    if (epsilon === 0) return "Median";
    return `Median ${epsilon > 0 ? "plus" : "minus"} ${num(Math.abs(epsilon))} standard deviation` + (Math.abs(epsilon) === 1 ? "" : "s");
  }
  function defaults(p0){
    const p = checkParams(p0), g = geometry(p), [[latA, lonA], [latB, lonB]] = p.trace;
    const shape = p.dip >= 90 ? "vertical" : `dipping ${num(p.dip)} degrees with a down-dip width of ${num(p.width_km)} km`;
    return {
      title: `M ${num(p.magnitude)} ${p.mechanism} scenario earthquake`,
      site_condition: `The same ground condition everywhere: Vs30 = ${num(p.vs30)} m/s. Local soil is not accounted for`,
      description: `${levelLabel(p.epsilon)} ground motions of a magnitude ${num(p.magnitude)} earthquake, ${p.mechanism} faulting, on a fault `
        + `from (${latA.toFixed(4)}, ${lonA.toFixed(4)}) to (${latB.toFixed(4)}, ${lonB.toFixed(4)}), ${g.length.toFixed(1)} km long, ${shape}. Computed with a ground-motion model, not recorded.`,
      source: {title: `Scenario computed with SR-HazardMaker using the ground-motion model of ${NAME}`, publisher: "",
               version: "BSSA14 base model: no regional adjustment, no basin term; RotD50 horizontal component"},
    };
  }
  function build(p0, meta){
    const p = checkParams(p0), g = geometry(p), grid = gridFor(p, g), nlat = grid.nlat, nlon = grid.nlon;
    const measures = {}; for (const m of MEASURES) measures[m] = new Array(nlat * nlon).fill(NODATA);
    for (let j = 0; j < nlat; j++){
      const lat = grid.lat_min + j * grid.dlat;
      for (let i = 0; i < nlon; i++){
        const r = rjb(g, lat, grid.lon_min + i * grid.dlon);
        for (const m of MEASURES) measures[m][j * nlon + i] = toInt(groundMotion(m, p.magnitude, p.mechanism, r, p.vs30, p.epsilon));
      }
    }
    return {
      format: FORMAT, id: meta.id, title: meta.title, kind: "scenario", description: meta.description || "", site_condition: meta.site_condition,
      units: "g", scale: SCALE, nodata: NODATA, grid, default_level: "event",
      levels: [{id: "event", label: levelLabel(p.epsilon), measures}],
      source: Object.assign({}, meta.source, {scenario: {
        magnitude: p.magnitude, mechanism: p.mechanism, trace: p.trace, length_km: Number(g.length.toFixed(3)), dip_deg: p.dip, down_dip_width_km: p.width_km,
        vs30_m_per_s: p.vs30, epsilon: p.epsilon, model: CITATION, model_options: "base model: no regional adjustment, no basin term", component: "RotD50",
        distance: "Joyner-Boore distance to the surface projection of a planar rectangular rupture, in a flat local frame"}}),
      provenance: {generator: `SR-HazardMaker ${H.VERSION}, browser (scenario builder)`, made_with: H.MADE_WITH, generated_utc: new Date().toISOString().replace(/\.\d+Z$/, "Z"), stored_precision_g: SCALE,
                   note: "Computed, not recorded. One Vs30 is used everywhere. With epsilon other than zero, every point is shifted by the same number of standard deviations, which is not a simulated realization of the event."},
    };
  }
  return {NAME, CITATION, COEFFS, LIMITS, MECHANISMS, DEFAULTS, lnMedian, sigma, groundMotion, checkInputs, checkParams, geometry, rjb, gridFor, levelLabel, defaults, build, num};
})();
if (typeof module !== "undefined" && module.exports) module.exports = SRScenario;
