#!/usr/bin/env python3
"""Draw the home-page hero artwork and write it into index.html.

The picture shows a strike-slip fault rupturing toward a city. The colored bands are
contours of a shaking-intensity field computed from a deliberately simple model:

  * distance to the ruptured part of the fault (intensity decays with distance)
  * directivity: stronger where the rupture runs toward a site, weaker behind it
  * uneven slip: two stronger patches along the fault
  * site heterogeneity: smooth random variation, plus a soft-soil basin that amplifies shaking

It is an illustration, not a ground-motion prediction. The parameters to adjust are in
intensity_field(): the directivity strengths, the patches, the basin, and the random seed.

Usage, from the repository root:
    python3 tools/build_hero.py

Requires numpy, scipy and contourpy.
"""
import math, re, sys
import numpy as np
from scipy.ndimage import gaussian_filter
import contourpy

RAMP = ['#D7263D', '#F46036', '#F9A03F', '#F2D16B', '#7BD389', '#38B6C9', '#3D7DD8', '#5B6FD6']      # strongest to weakest


def windows(xs, ys, w, h, fill):
    return ''.join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"></rect>' for y in ys for x in xs)

def cluster1(fill, stroke, win, sw=1):
    g = f'<g fill="{fill}" stroke="{stroke}" stroke-width="{sw}">'
    for x, y, w, h in [(592,442,38,78),(634,404,48,116),(686,356,46,164),(736,418,38,102),(778,452,40,68)]:
        g += f'<rect x="{x}" y="{y}" width="{w}" height="{h}"></rect>'
    g += '</g>'
    g += f'<path d="M709 356 V330" fill="none" stroke="{stroke}" stroke-width="2" stroke-linecap="round"></path>'
    g += windows([642,656,670], [414,434,454,474], 6, 8, win)
    g += windows([694,706,718], [370,390,410,430,450,470], 6, 8, win)
    return g

def cluster2(fill, stroke, win, sw=1):
    g = f'<g fill="{fill}" stroke="{stroke}" stroke-width="{sw}">'
    for x, y, w, h in [(1214,432,42,88),(1262,328,54,192),(1324,392,44,128),(1376,446,64,74)]:
        g += f'<rect x="{x}" y="{y}" width="{w}" height="{h}"></rect>'
    g += '</g>'
    g += f'<path d="M1289 328 V296" fill="none" stroke="{stroke}" stroke-width="2" stroke-linecap="round"></path>'
    g += windows([1272,1286,1300], [344,366,388,410,432,454,476], 7, 9, win)
    return g

def susp_bridge(fill, stroke, cable, sw=1, deep=0):
    g = f'<g fill="{fill}" stroke="{stroke}" stroke-width="{sw}">'
    g += '<rect x="850" y="486" width="336" height="7"></rect>'
    g += f'<rect x="866" y="493" width="8" height="{27+deep}"></rect><rect x="1170" y="493" width="8" height="{27+deep}"></rect>'
    g += f'<rect x="920" y="380" width="12" height="{140+deep}"></rect><rect x="1110" y="380" width="12" height="{140+deep}"></rect>'
    g += '<rect x="916" y="420" width="20" height="5"></rect><rect x="1106" y="420" width="20" height="5"></rect></g>'
    g += f'<g fill="none" stroke="{cable}" stroke-linecap="round">'
    g += '<path d="M850 486 Q890 450 926 380" stroke-width="2.6"></path><path d="M926 380 Q1021 520 1116 380" stroke-width="2.6"></path><path d="M1116 380 Q1152 450 1186 486" stroke-width="2.6"></path>'
    g += '<path d="M950 411 V486 M980 437 V486 M1010 449 V486 M1040 447 V486 M1070 431 V486 M1095 408 V486" stroke-width="1.4"></path></g>'
    return g

def shakes(color, which=('b1','b2','deck','via'), op=0.9, sw=2):
    d = {'b1': 'M676 366 q-8 14 0 28 M666 362 q-11 18 0 36 M742 366 q8 14 0 28 M752 362 q11 18 0 36',
         'b2': 'M1252 338 q-8 14 0 28 M1242 334 q-11 18 0 36 M1326 338 q8 14 0 28 M1336 334 q11 18 0 36',
         'deck': 'M982 472 q8 -8 16 0 t16 0 t16 0 t16 0', 'via': 'M392 482 q8 -8 16 0 t16 0 t16 0'}
    return f'<path d="{" ".join(d[k] for k in which)}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" opacity="{op}"></path>'


W, H = 1800, 750                  # drawing space; shown at 80% of the earlier scale
GY = 670                          # ground line

# ---- rupture geometry (drawing units) ----
A = np.array([935.0, 40.0]); B = np.array([1065.0, 640.0])     # fault trace
T0, T1, TH = 0.10, 0.92, 0.26                                  # rupture extent and hypocenter along the trace
P = lambda t: A + (B - A) * t
RA, RB, HYP = P(T0), P(T1), P(TH)
U = (B - A) / np.linalg.norm(B - A)                            # strike direction (rupture runs along +U)
N = np.array([U[1], -U[0]])                                    # normal, pointing right

def intensity_field(step=5, pad=320, seed=7):
    xs = np.arange(-pad, W + pad + step, step, dtype=float); ys = np.arange(-pad, H + pad + step, step, dtype=float)
    X, Y = np.meshgrid(xs, ys)
    L = np.linalg.norm(RB - RA)
    # closest point on the rupture and distance to it
    s = np.clip(((X - RA[0]) * U[0] + (Y - RA[1]) * U[1]) / L, 0, 1)
    R = np.hypot(X - (RA[0] + s * L * U[0]), Y - (RA[1] + s * L * U[1]))
    base = -np.log1p(R / 95.0)
    # directivity: stronger where the rupture runs toward the site, weaker behind it
    sh = (TH - T0) / (T1 - T0)
    dx, dy = X - HYP[0], Y - HYP[1]
    cos_t = (dx * U[0] + dy * U[1]) / np.maximum(np.hypot(dx, dy), 1e-6)
    fwd = np.clip((s - sh) / (1 - sh), 0, 1) * np.clip(cos_t, 0, 1)
    back = np.clip((sh - s) / sh, 0, 1) * np.clip(-cos_t, 0, 1)
    directivity = 0.62 * fwd - 0.30 * back
    # uneven slip: two stronger patches along the fault
    asp = np.zeros_like(X)
    for t, amp, rad in [(0.50, 0.30, 120.0), (0.80, 0.36, 105.0)]:
        c = P(t); asp += amp * np.exp(-((X - c[0]) ** 2 + (Y - c[1]) ** 2) / (2 * rad ** 2))
    # site heterogeneity: smooth random variation at two scales, plus a soft-soil basin that amplifies shaking
    rng = np.random.default_rng(seed)
    def smooth(sig):
        f = gaussian_filter(rng.standard_normal(X.shape), sig); return f / f.std()
    site = 0.17 * smooth(15) + 0.21 * smooth(36)
    basin = 0.78 * np.exp(-(((X - 1470) / 150.0) ** 2 + ((Y - 430) / 95.0) ** 2))
    Z = base + directivity + asp + site + basin
    Z = gaussian_filter(Z, 1.2)
    Z[0, :] = Z[-1, :] = Z[:, 0] = Z[:, -1] = Z.min() - 5            # close every contour inside the grid
    return xs, ys, Z

def simplify(pts, tol=0.8):
    """Douglas-Peucker. A closed ring is split at the point farthest from its start, so the
    two halves each have distinct end points."""
    if len(pts) < 4: return pts
    keep = np.zeros(len(pts), bool); keep[0] = keep[-1] = True
    if np.allclose(pts[0], pts[-1]):
        far = int(np.argmax(np.hypot(*(pts - pts[0]).T)))
        keep[far] = True
        stack = [(0, far), (far, len(pts) - 1)]
    else:
        stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1: continue
        seg = pts[j] - pts[i]; n = np.hypot(*seg)
        d = np.abs(seg[0] * (pts[i+1:j, 1] - pts[i, 1]) - seg[1] * (pts[i+1:j, 0] - pts[i, 0])) / (n if n else 1)
        k = int(np.argmax(d))
        if d[k] > tol:
            k += i + 1; keep[k] = True; stack += [(i, k), (k, j)]
    return pts[keep]

def contours():
    xs, ys, Z = intensity_field()
    cg = contourpy.contour_generator(xs, ys, Z)
    levels = [-math.log1p(r / 95.0) for r in (34, 78, 132, 196, 270, 356, 458, 580)]   # strongest first
    out = []
    for lv in levels:
        d = ''
        for ring in cg.lines(lv):
            if len(ring) < 12: continue
            p = simplify(np.asarray(ring))
            # skip rings entirely outside the picture
            if p[:, 0].max() < -20 or p[:, 0].min() > W + 20 or p[:, 1].max() < -20 or p[:, 1].min() > H + 20: continue
            d += 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in p[:-1]) + 'Z '
        out.append(d.strip())
    return out

def trace(y, bursts, width=W):
    """Ground-motion record: flat line with wavelets at (center, amplitude)."""
    pat = [(8, -0.18), (10, 0.45), (10, -0.68), (10, 0.87), (12, -1.0), (12, 0.92), (10, -0.76), (10, 0.55), (10, -0.37), (8, 0.16), (8, 0.04)]
    wlen = sum(dx for dx, _ in pat)
    d, x = f'M0 {y}', 0
    for c, amp in sorted(bursts):
        start = c - wlen / 2
        d += f' h{start - x:.0f} ' + ' '.join(f'l{dx} {amp * f:.1f}' for dx, f in pat)
        x = start + wlen
    return d + f' h{width - x:.0f}'

def scene():
    bg, edge, white, dark, win = '#0F1A2B', '#32486A', '#F5F7FA', '#080E18', '#17243A'
    s = f'<rect width="{W}" height="{H}" fill="{bg}"></rect>'
    rings = contours()
    def tint(c, a):                                                   # the band color mixed into the background
        m = lambda i: round(int(bg[i:i+2], 16) * (1 - a) + int(c[i:i+2], 16) * a)
        return '#%02X%02X%02X' % (m(1), m(3), m(5))
    alphas = [0.30, 0.27, 0.24, 0.21, 0.18, 0.16, 0.14, 0.12]
    for d, c, a in reversed(list(zip(rings, RAMP, alphas))):          # one clean tint per band, weakest first
        if d: s += f'<path d="{d}" fill="{tint(c, a)}" fill-rule="evenodd"></path>'
    sw = [1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2]; op = [1, 0.95, 0.9, 0.85, 0.78, 0.7, 0.62, 0.54]
    for i, (d, c) in enumerate(zip(rings, RAMP)):
        if d: s += f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw[i]}" stroke-linejoin="round" opacity="{op[i]}"></path>'
    # fault trace, rupture-direction arrow, hypocenter
    a2, b2 = A + N * 9, B + N * 9
    s += f'<path d="M{a2[0]:.0f} {a2[1]:.0f} L{b2[0]:.0f} {b2[1]:.0f}" stroke="{white}" stroke-width="1" stroke-dasharray="4 6" opacity="0.45" fill="none"></path>'
    s += f'<path d="M{A[0]:.0f} {A[1]:.0f} L{B[0]:.0f} {B[1]:.0f}" stroke="{white}" stroke-width="2.6" stroke-linecap="round" fill="none"></path>'
    e0, e1 = P(0.34) + N * 26, P(0.60) + N * 26
    h1, h2 = e1 - U * 13 + N * 6, e1 - U * 13 - N * 6
    s += (f'<path d="M{e0[0]:.1f} {e0[1]:.1f} L{e1[0]:.1f} {e1[1]:.1f} M{h1[0]:.1f} {h1[1]:.1f} L{e1[0]:.1f} {e1[1]:.1f} L{h2[0]:.1f} {h2[1]:.1f}" '
          f'fill="none" stroke="{white}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.85"></path>')
    s += f'<circle cx="{HYP[0]:.0f}" cy="{HYP[1]:.0f}" r="12" fill="none" stroke="{white}" stroke-width="1.5"></circle><circle cx="{HYP[0]:.0f}" cy="{HYP[1]:.0f}" r="5.5" fill="#D7263D"></circle>'
    # ground and structures
    s += f'<rect x="0" y="{GY}" width="{W}" height="{H - GY}" fill="#0A121F"></rect>'
    sw_s = 0.8
    s += f'<g fill="{dark}" stroke="{edge}" stroke-width="{sw_s}">'
    s += f'<path d="M0 {GY} L0 618 L70 596 L130 606 L205 578 L270 604 L330 636 L362 {GY} Z"></path>'
    s += f'<rect x="306" y="644" width="530" height="6"></rect>'
    for x in (386, 476, 566, 656, 746):
        s += f'<rect x="{x}" y="650" width="8" height="20"></rect>'
    for x, y, w, h in [(1712, 612, 40, 58), (1756, 588, 44, 82)]:
        s += f'<rect x="{x}" y="{y}" width="{w}" height="{h}"></rect>'
    s += '</g>'
    s += f'<path d="M262 {GY} v-22 a22 22 0 0 1 44 0 v22 Z" fill="{win}" stroke="#3E5680" stroke-width="1.1"></path>'
    s += windows([1764, 1778], [598, 616, 634], 7, 9, win)
    dy = GY - 520
    s += f'<g transform="translate(250 {dy})">{cluster1(dark, edge, win, sw_s)}{susp_bridge(dark, edge, edge, sw_s)}{cluster2(dark, edge, win, sw_s)}{shakes(white, ("b1", "b2", "deck"), 0.9, 1.4)}</g>'
    s += f'<path d="M520 632 q8 -8 16 0 t16 0 t16 0" fill="none" stroke="{white}" stroke-width="1.4" stroke-linecap="round" opacity="0.9"></path>'
    s += f'<path d="{trace(712, [(240, 5), (520, 9), (800, 17), (1060, 38), (1290, 22), (1500, 30), (1700, 8)])}" fill="none" stroke="{white}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"></path>'
    return s


def main(path='index.html'):
    html = open(path, encoding='utf-8').read()
    a = html.index('<svg class="hero-art"')
    b = html.index('</svg>', a) + len('</svg>')
    svg = ('<svg class="hero-art" viewBox="0 0 %d %d" preserveAspectRatio="xMidYMax slice" role="img" '
           'aria-label="A fault rupturing toward a city. Irregular bands of color show shaking intensity, strongest in red along the fault '
           'and ahead of the rupture, weakening to blue with distance, reaching a tunnel, a viaduct, buildings and a suspension bridge.">\n'
           % (W, H) + scene() + '\n</svg>')
    open(path, 'w', encoding='utf-8').write(html[:a] + svg + html[b:])
    print('hero artwork written to %s (%d bytes)' % (path, len(svg)))


if __name__ == '__main__':
    main(*sys.argv[1:2])
