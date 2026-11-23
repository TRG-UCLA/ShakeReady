/* SPDX-License-Identifier: BSD-3-Clause
   Copyright (c) 2026, E. Taciroglu. Part of SR-SuiteMaker; see LICENSE. */
/* SR-SuiteMaker's charts, drawn as SVG text with no outside library: spectra, a hazard curve, and a hazard
   disaggregation in two views. Each function returns an <svg> element as a string, sized by its viewBox. */
"use strict";
const SRPlots = (() => {
  const INK = "#22303C", SUB = "#5F7183", RULE = "#D8E0E7", NAVY = "#0F1A2B", RED = "#D7263D", BLUE = "#3D7DD8";
  const EPS = ["#2B4C8C", "#3F6DB3", "#6C93CF", "#9DB8E0", "#C9D8EE", "#E6ECF4", "#F6E4DC", "#F2C2AE", "#E99A80", "#DB6B55", "#C23B33", "#8E1B1F"];
  const SEQ = ["#FFFDE8", "#FFF3B0", "#FED98E", "#FDB863", "#F46036", "#C1121F", "#5A0F2E"], BRK = [0.1, 0.5, 1, 2.5, 5, 10];
  const f1 = v => v.toFixed(1), num = v => String(Number(v.toPrecision(6)));
  const svg = (w, h, body, label) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${label}" font-family="Archivo, system-ui, Arial, sans-serif" style="width:100%;height:auto;display:block">${body}</svg>`;
  const shade = (hex, f) => "#" + [1, 3, 5].map(i => Math.max(0, Math.min(255, Math.round(parseInt(hex.slice(i, i + 2), 16) * f))).toString(16).padStart(2, "0")).join("");
  /* tick values for a logarithmic axis: 1, 2, 5 in each decade */
  function logTicks(lo, hi){
    const out = [];
    for (let d = Math.floor(Math.log10(lo)); d <= Math.ceil(Math.log10(hi)); d++) for (const m of [1, 2, 5]){ const v = m * Math.pow(10, d); if (v >= lo * 0.999 && v <= hi * 1.001) out.push(Number(v.toPrecision(1))); }
    return out;
  }
  function logFrame(X0, Y0, W, H, xr, yr, xLabel, yLabel, xTicks, yTicks){
    const lx = v => X0 + (Math.log(v) - Math.log(xr[0])) / (Math.log(xr[1]) - Math.log(xr[0])) * W;
    const ly = v => Y0 + (1 - (Math.log(Math.min(Math.max(v, yr[0]), yr[1])) - Math.log(yr[0])) / (Math.log(yr[1]) - Math.log(yr[0]))) * H;
    let g = "";
    for (const t of xTicks) g += `<line x1="${f1(lx(t))}" y1="${Y0}" x2="${f1(lx(t))}" y2="${Y0 + H}" stroke="${RULE}"/><text x="${f1(lx(t))}" y="${Y0 + H + 18}" font-size="12" fill="${SUB}" text-anchor="middle">${num(t)}</text>`;
    for (const t of yTicks) g += `<line x1="${X0}" y1="${f1(ly(t))}" x2="${X0 + W}" y2="${f1(ly(t))}" stroke="${RULE}"/><text x="${X0 - 8}" y="${f1(ly(t) + 4)}" font-size="12" fill="${SUB}" text-anchor="end">${t < 0.001 ? t.toExponential(0).replace("e-", "e−") : num(t)}</text>`;
    g += `<text x="${X0 + W / 2}" y="${Y0 + H + 40}" font-size="13" fill="${INK}" text-anchor="middle">${xLabel}</text><text transform="translate(${X0 - 52} ${Y0 + H / 2}) rotate(-90)" font-size="13" fill="${INK}" text-anchor="middle">${yLabel}</text>`;
    return {lx, ly, g};
  }
  const path = (xs, ys, lx, ly) => "M" + xs.map((x, i) => `${f1(lx(x))} ${f1(ly(ys[i]))}`).join(" L");

  /* The uniform hazard spectrum and the target built from it. */
  function spectra(uhs, target, opts){
    const o = opts || {}, X0 = 70, Y0 = 16, W = 660, H = 330;
    const all = uhs.sa.concat(target ? target.sa : []), top = Math.max(...all) * 1.4, bot = Math.max(Math.min(...all) / 1.6, top / 2000);
    const yr = [Math.pow(10, Math.floor(Math.log10(bot) * 3) / 3), Math.pow(10, Math.ceil(Math.log10(top) * 3) / 3)];
    const F = logFrame(X0, Y0, W, H, [0.01, 10], yr, "Period, s", "Spectral acceleration, g", [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10], logTicks(yr[0], yr[1]));
    let b = F.g;
    if (target && target.sigma_ln){
      const up = target.sa.map((v, i) => v * Math.exp(target.sigma_ln[i])), dn = target.sa.map((v, i) => v * Math.exp(-target.sigma_ln[i]));
      b += `<path d="${path(target.periods, up, F.lx, F.ly)} L${target.periods.slice().reverse().map((t, i) => `${f1(F.lx(t))} ${f1(F.ly(dn[dn.length - 1 - i]))}`).join(" L")} Z" fill="${BLUE}" opacity="0.14"/>`;
    }
    b += `<path d="${path(uhs.periods, uhs.sa, F.lx, F.ly)}" fill="none" stroke="${NAVY}" stroke-width="2.6"/>` + uhs.periods.map((t, i) => `<circle cx="${f1(F.lx(t))}" cy="${f1(F.ly(uhs.sa[i]))}" r="2.8" fill="${NAVY}"/>`).join("");
    if (target){
      b += `<path d="${path(target.periods, target.sa, F.lx, F.ly)}" fill="none" stroke="${RED}" stroke-width="2.6" stroke-dasharray="8 4"/>`;
      const ts = target.definition.conditioning_period_s, k = target.periods.indexOf(ts);
      if (k >= 0) b += `<circle cx="${f1(F.lx(ts))}" cy="${f1(F.ly(target.sa[k]))}" r="6" fill="#fff" stroke="${RED}" stroke-width="2.4"/>`;
    }
    const L = Y0 + H + 62;
    b += `<g font-size="12.5" fill="${INK}"><line x1="70" y1="${L}" x2="100" y2="${L}" stroke="${NAVY}" stroke-width="2.6"/><text x="106" y="${L + 4}">Uniform hazard spectrum, ${Number(uhs.return_period).toLocaleString("en-US")} years</text>`
      + (target ? `<line x1="350" y1="${L}" x2="380" y2="${L}" stroke="${RED}" stroke-width="2.6" stroke-dasharray="8 4"/><text x="386" y="${L + 4}">Target: conditional mean spectrum</text><rect x="608" y="${L - 6}" width="24" height="12" fill="${BLUE}" opacity="0.25"/><text x="638" y="${L + 4}">± 1 sd</text>` : "") + `</g>`;
    return svg(760, L + 16, b, o.label || "Uniform hazard spectrum and target spectrum");
  }

  /* One hazard curve, with the return period and the ground motion it gives marked. */
  function hazardCurve(curve, returnPeriod, groundMotion, name){
    const X0 = 70, Y0 = 16, W = 660, H = 260;
    const pts = curve.x.map((x, i) => [x, curve.y[i]]).filter(p => p[0] > 0 && p[1] > 1e-7);
    const xr = [Math.pow(10, Math.floor(Math.log10(pts[0][0]))), Math.pow(10, Math.ceil(Math.log10(pts[pts.length - 1][0])))], yr = [1e-6, 1];
    const F = logFrame(X0, Y0, W, H, xr, yr, `${name}, g`, "Annual rate of exceedance", logTicks(xr[0], xr[1]), [1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1]);
    const rate = 1 / returnPeriod;
    let b = F.g + `<path d="${path(pts.map(p => p[0]), pts.map(p => p[1]), F.lx, F.ly)}" fill="none" stroke="${NAVY}" stroke-width="2.6"/>`;
    b += `<line x1="${X0}" y1="${f1(F.ly(rate))}" x2="${f1(F.lx(groundMotion))}" y2="${f1(F.ly(rate))}" stroke="${RED}" stroke-width="1.6" stroke-dasharray="5 4"/><line x1="${f1(F.lx(groundMotion))}" y1="${f1(F.ly(rate))}" x2="${f1(F.lx(groundMotion))}" y2="${Y0 + H}" stroke="${RED}" stroke-width="1.6" stroke-dasharray="5 4"/>`
      + `<circle cx="${f1(F.lx(groundMotion))}" cy="${f1(F.ly(rate))}" r="5.5" fill="#fff" stroke="${RED}" stroke-width="2.4"/>`
      + `<text x="${f1(F.lx(groundMotion) + 10)}" y="${f1(F.ly(rate) - 9)}" font-size="12.5" fill="#9C1B2C">${groundMotion.toFixed(3)} g once in ${Number(returnPeriod).toLocaleString("en-US")} years</text>`;
    return svg(760, Y0 + H + 52, b, `Hazard curve for ${name}`);
  }

  /* The disaggregation's cells laid out on a grid, shared by both views. */
  function cells(detail){
    const bins = detail.bins.map(b => ({r: b.r, m: Math.round(b.m * 10) / 10, eps: b.eps, total: b.eps.reduce((a, e) => a + e[1], 0)})).filter(b => b.total >= 0.02);
    if (!bins.length) return null;
    const r0 = Math.min(...bins.map(b => b.r)), r1 = Math.max(...bins.map(b => b.r)), m1 = Math.max(...bins.map(b => b.m)), m0 = Math.min(5.1, Math.min(...bins.map(b => b.m)));
    const dr = 20, dm = 0.2, rs = [], ms = [];
    for (let k = 0; k <= Math.round((r1 - r0) / dr); k++) rs.push(r0 + dr * k);
    for (let k = 0; k <= Math.round((m1 - m0) / dm); k++) ms.push(Math.round((m0 + dm * k) * 10) / 10);
    const grid = new Map(bins.map(b => [`${b.r}|${b.m}`, b]));
    return {rs, ms, dr, dm, at: (i, j) => grid.get(`${rs[i]}|${ms[j]}`), zmax: Math.max(...bins.map(b => b.total))};
  }

  /* Bars on a grid of distance against magnitude, stacked by epsilon. */
  function disaggBars(detail){
    const G = cells(detail); if (!G) return "";
    const nr = G.rs.length, nm = G.ms.length, C30 = Math.cos(Math.PI / 6), S30 = Math.sin(Math.PI / 6);
    const DI = Math.max(1.2, Math.min(2.6, 10 / nr));            // distance rows are drawn deep enough not to collapse into a strip
    const ZR = 0.62 * (nr * DI + nm) * S30 / G.zmax;
    const raw = (i, j, z) => [(j - i * DI) * C30, (i * DI + j) * S30 - (z || 0) * ZR];
    const cs = []; for (const i of [0, nr]) for (const j of [0, nm]) for (const z of [0, G.zmax * 1.08]) cs.push(raw(i, j, z));
    const x0 = Math.min(...cs.map(c => c[0])), x1 = Math.max(...cs.map(c => c[0])), y0 = Math.min(...cs.map(c => c[1])), y1 = Math.max(...cs.map(c => c[1]));
    const BX = 78, BY = 18, BW = 520, BH = 330, F = Math.min(BW / (x1 - x0), BH / (y1 - y0));
    const P = (i, j, z) => { const [x, y] = raw(i, j, z); return [BX + (x - x0) * F, BY + (y - y0) * F]; };
    const poly = (pts, fill, stroke) => `<polygon points="${pts.map(p => `${f1(p[0])},${f1(p[1])}`).join(" ")}" fill="${fill}" stroke="${stroke || INK}" stroke-width="0.5" stroke-linejoin="round"/>`;
    const line = (a, c, col) => `<line x1="${f1(a[0])}" y1="${f1(a[1])}" x2="${f1(c[0])}" y2="${f1(c[1])}" stroke="${col}" stroke-width="0.7"/>`;
    let b = poly([P(0, 0), P(nr, 0), P(nr, nm), P(0, nm)], "#F1F4F7", "#B9C5D0");
    for (let i = 0; i <= nr; i++) b += line(P(i, 0), P(i, nm), "#D2DAE2");
    for (let j = 0; j <= nm; j++) b += line(P(0, j), P(nr, j), "#D2DAE2");
    b += line(P(0, 0), P(0, 0, G.zmax * 1.05), SUB);
    for (const z of [1, 2, 5, 10, 15, 20, 25, 30, 40, 50].filter(v => v <= G.zmax * 1.05 && v >= G.zmax / 6)){ const q = P(0, 0, z); b += `<line x1="${f1(q[0] - 6)}" y1="${f1(q[1])}" x2="${f1(q[0])}" y2="${f1(q[1])}" stroke="${SUB}"/><text x="${f1(q[0] - 9)}" y="${f1(q[1] + 4)}" font-size="11.5" fill="${SUB}" text-anchor="end">${z}%</text>`; }
    const order = [];
    for (let i = 0; i < nr; i++) for (let j = 0; j < nm; j++) if (G.at(i, j)) order.push([i, j]);
    order.sort((p, q) => (p[0] * DI + p[1]) - (q[0] * DI + q[1]) || p[0] - q[0]);                 // back to front
    for (const [i, j] of order){
      const cell = G.at(i, j), by = new Map(cell.eps), i0 = i + 0.10, i1 = i + 0.90, j0 = j + 0.12, j1 = j + 0.88;
      let z0 = 0, top = 0;
      for (let k = 0; k < 12; k++){
        const v = by.get(k) || 0; if (v <= 0) continue;
        const z1 = z0 + v; top = k;
        b += poly([P(i1, j0, z0), P(i1, j1, z0), P(i1, j1, z1), P(i1, j0, z1)], shade(EPS[k], 0.84)) + poly([P(i0, j1, z0), P(i1, j1, z0), P(i1, j1, z1), P(i0, j1, z1)], shade(EPS[k], 0.66));
        z0 = z1;
      }
      b += poly([P(i0, j0, z0), P(i1, j0, z0), P(i1, j1, z0), P(i0, j1, z0)], EPS[top]);
    }
    for (let j = 0; j < nm; j += 2){ const q = P(nr, j + 0.5); b += `<text x="${f1(q[0] - 7)}" y="${f1(q[1] + 15)}" font-size="11.5" fill="${SUB}" text-anchor="end">${G.ms[j].toFixed(1)}</text>`; }
    let q = P(nr, nm / 2); b += `<text transform="translate(${f1(q[0] - 46)} ${f1(q[1] + 44)}) rotate(30)" font-size="13" fill="${INK}" text-anchor="middle">Magnitude</text>`;
    const stepR = nr > 6 ? 2 : 1;
    for (let i = 0; i < nr; i += stepR){ q = P(i + 0.5, nm); b += `<text x="${f1(q[0] + 8)}" y="${f1(q[1] + 5)}" font-size="11.5" fill="${SUB}">${G.rs[i] - G.dr / 2}–${G.rs[i] + G.dr / 2} km</text>`; }
    q = P(nr / 2, nm); b += `<text transform="translate(${f1(q[0] + 78)} ${f1(q[1] + 26)}) rotate(-30)" font-size="13" fill="${INK}" text-anchor="middle">Distance to rupture</text>`;
    const LY = BY + BH + 64;
    b += `<text x="60" y="${LY - 8}" font-size="12.5" fill="${INK}">Epsilon: how far above or below the median the ground motion must be</text>` + EPS.map((c, k) => `<rect x="${60 + k * 46}" y="${LY}" width="46" height="13" fill="${c}" stroke="#fff"/>`).join("")
      + `<text x="60" y="${LY + 29}" font-size="11.5" fill="${SUB}">−2.5</text><text x="336" y="${LY + 29}" font-size="11.5" fill="${SUB}" text-anchor="middle">0</text><text x="612" y="${LY + 29}" font-size="11.5" fill="${SUB}" text-anchor="end">+2.5</text>`;
    return svg(680, LY + 38, b, "Hazard disaggregation: contribution by magnitude, distance and epsilon");
  }

  /* The same grid from above, colored by contribution, with totals along the edges. */
  function disaggMap(detail){
    const G = cells(detail); if (!G) return "";
    const nr = G.rs.length, nm = G.ms.length, FX = 78, FY = 84, CW = Math.min(22, 360 / nm), CH = Math.min(34, 240 / nr);
    const col = v => { let k = 0; while (k < BRK.length && v >= BRK[k]) k++; return SEQ[k]; };
    let b = "";
    const byM = new Array(nm).fill(0), byR = new Array(nr).fill(0);
    for (let i = 0; i < nr; i++) for (let j = 0; j < nm; j++){
      const cell = G.at(i, j); if (cell){ byM[j] += cell.total; byR[i] += cell.total; }
      b += `<rect x="${f1(FX + j * CW)}" y="${f1(FY + i * CH)}" width="${f1(CW)}" height="${f1(CH)}" fill="${cell ? col(cell.total) : "#F7F9FB"}" stroke="#fff"/>`;
    }
    byM.forEach((v, j) => { const h = 60 * v / Math.max(...byM); b += `<rect x="${f1(FX + j * CW + 2)}" y="${f1(FY - 8 - h)}" width="${f1(CW - 4)}" height="${f1(h)}" fill="${SUB}"/>`; });
    byR.forEach((v, i) => { const w = 56 * v / Math.max(...byR); b += `<rect x="${f1(FX + nm * CW + 8)}" y="${f1(FY + i * CH + 4)}" width="${f1(w)}" height="${f1(CH - 8)}" fill="${SUB}"/><text x="${f1(FX + nm * CW + 14 + w)}" y="${f1(FY + i * CH + CH / 2 + 4)}" font-size="11.5" fill="${INK}">${v.toFixed(0)}%</text>`; });
    for (let j = 0; j < nm; j += 2) b += `<text x="${f1(FX + j * CW + CW / 2)}" y="${f1(FY + nr * CH + 16)}" font-size="11.5" fill="${SUB}" text-anchor="middle">${G.ms[j].toFixed(1)}</text>`;
    for (let i = 0; i < nr; i += nr > 8 ? 2 : 1) b += `<text x="${FX - 6}" y="${f1(FY + i * CH + CH / 2 + 4)}" font-size="11.5" fill="${SUB}" text-anchor="end">${G.rs[i] - G.dr / 2}–${G.rs[i] + G.dr / 2}</text>`;
    const by = FY + nr * CH;
    b += `<text x="${f1(FX + nm * CW / 2)}" y="${f1(by + 38)}" font-size="13" fill="${INK}" text-anchor="middle">Magnitude</text><text transform="translate(${FX - 58} ${f1(FY + nr * CH / 2)}) rotate(-90)" font-size="13" fill="${INK}" text-anchor="middle">Distance, km</text>`;
    const mark = (m, r, c) => `<circle cx="${f1(FX + (m - (G.ms[0] - G.dm / 2)) / G.dm * CW)}" cy="${f1(FY + (r - (G.rs[0] - G.dr / 2)) / G.dr * CH)}" r="6" fill="none" stroke="${c}" stroke-width="2.6"/>`;
    b += mark(detail.mean.magnitude, detail.mean.distance_km, NAVY) + (detail.mode.magnitude !== null ? mark(detail.mode.magnitude, detail.mode.distance_km, "#1D9BD8") : "");
    b += `<g font-size="12" fill="${INK}"><circle cx="${FX + 6}" cy="${f1(by + 62)}" r="5.5" fill="none" stroke="${NAVY}" stroke-width="2.6"/><text x="${FX + 18}" y="${f1(by + 66)}">mean: M ${detail.mean.magnitude}, ${detail.mean.distance_km} km</text>`
      + (detail.mode.magnitude !== null ? `<circle cx="${FX + 186}" cy="${f1(by + 62)}" r="5.5" fill="none" stroke="#1D9BD8" stroke-width="2.6"/><text x="${FX + 198}" y="${f1(by + 66)}">mode: M ${detail.mode.magnitude}, ${detail.mode.distance_km} km</text>` : "") + `</g>`;
    const LY = by + 104;
    b += `<text x="${FX}" y="${f1(LY - 8)}" font-size="12.5" fill="${INK}">Percent contribution to the hazard, by cell</text>` + SEQ.map((c, k) => `<rect x="${FX + k * 40}" y="${f1(LY)}" width="40" height="13" fill="${c}" stroke="#fff"/>`).join("") + BRK.map((v, k) => `<text x="${FX + (k + 1) * 40}" y="${f1(LY + 29)}" font-size="11.5" fill="${SUB}" text-anchor="middle">${v}</text>`).join("");
    return svg(560, LY + 38, b, "Hazard disaggregation seen from above, with totals by magnitude and by distance");
  }
  return {spectra, hazardCurve, disaggBars, disaggMap, EPS, SEQ};
})();
if (typeof module !== "undefined" && module.exports) module.exports = SRPlots;
