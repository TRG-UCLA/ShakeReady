#!/usr/bin/env python3
"""Structural damage of concrete buildings by the two methods of the Hazus manual: a reference calculation.

Part of ShakeReady. Made by E. Taciroglu.

    python3 tools/hazus_buildings.py          runs the self-test and writes data/fragility/hazus_concrete_buildings.json
                                              (from the repository root)

Source: FEMA, Hazus Earthquake Model Technical Manual, Hazus 6.1, July 2024
(fema_hazus-earthquake-model-technical-manual-6-1.pdf, SHA-256 59b7e55a...5754). It covers the twelve classes of the
LA concrete-building inventory: types C2 (concrete shear walls) and C3 (concrete frame with unreinforced masonry
infill), low-, mid- and high-rise, at the Low-Code and Pre-Code design levels.

Method 1, capacity spectrum (manual sections 5.4.1, 5.4.2 and 5.6.1). The building's capacity curve is intersected
with the demand spectrum, reduced for the damping the building develops, to find its peak spectral displacement.
The damage-state probabilities are read from the spectral-displacement curves of Tables 5-21 and 5-22.

Method 2, equivalent PGA (manual section 5.4.3). Lognormal curves on peak ground acceleration, Tables 5-39 and 5-40.
The manual gives them as guidance for buildings of utility and transportation systems and says Hazus itself does not
currently use them. They are for a reference spectrum shape (a large western US earthquake, soil Site Class D, 15 km
or more from the source) and Equation 5-6 converts their medians to other spectrum shapes.

WHAT WAS READ FROM THE MANUAL, AND HOW
  Tables 5-14, 5-15, 5-39, 5-40 and 5-42: read from the manual's text by script and then compared, row by row, with
  images of the pages (2026-11-27). The spectral-displacement curves (Tables 5-21, 5-22) were transcribed and checked
  earlier and are read here from data/fragility/hazus_ndrcb_la_classes.json.
  Equations 4-2, 4-3, 4-4 and 5-6 to 5-15: these are images in the PDF. Each was read by eye from the rendered page
  and is written out beside the code that uses it.

WHAT THE MANUAL DOES NOT SAY
  Method 1 cannot be computed from the manual alone. It leaves out the elastic damping of each building type, the
  form of the capacity curve between its yield and ultimate points, and how the area of the hysteresis loop is
  taken; and Equation 5-10 as printed mixes a percentage with a fraction. Each such point is a choice, listed under
  CHOICES with its identifier and basis, so that results can be traced and the choice reviewed. The project lead was
  shown them, with what they change, and approved them on 2026-11-28.

The dashboard repeats this calculation in the browser from the file this script writes; tools/tests/test_dashboard.py
requires the two to give the same table for every building (tools/building_damage_reference.py makes the table here).
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATES = ("None", "Slight", "Moderate", "Extensive", "Complete")
TYPES = ("C2L", "C2M", "C2H", "C3L", "C3M", "C3H")
LEVELS = {"LC": "Low-Code", "PC": "Pre-Code"}

# ---------------------------------------------------------------------------------------------------------------------
# Tables, as printed in the manual
# ---------------------------------------------------------------------------------------------------------------------
# Tables 5-14 (Low-Code) and 5-15 (Pre-Code), capacity curves: yield point Dy (in), Ay (g); ultimate point Du (in), Au (g).
# The two tables give the same values for these six types.
CAPACITY = {
    "C2L": (0.12, 0.100, 1.499, 0.250), "C2M": (0.26, 0.083, 2.163, 0.208), "C2H": (0.735, 0.063, 4.593, 0.159),
    "C3L": (0.12, 0.100, 1.349, 0.225), "C3M": (0.26, 0.083, 1.946, 0.188), "C3H": (0.735, 0.063, 4.134, 0.143),
}
# Tables 5-39 (Low-Code) and 5-40 (Pre-Code), equivalent-PGA medians in g: slight, moderate, extensive, complete.
EQUIVALENT_PGA = {
    "LC": {"C2L": (0.14, 0.19, 0.30, 0.52), "C2M": (0.12, 0.19, 0.38, 0.63), "C2H": (0.11, 0.19, 0.38, 0.65),
           "C3L": (0.12, 0.17, 0.26, 0.44), "C3M": (0.11, 0.17, 0.32, 0.51), "C3H": (0.09, 0.16, 0.33, 0.53)},
    "PC": {"C2L": (0.11, 0.15, 0.24, 0.42), "C2M": (0.10, 0.15, 0.30, 0.50), "C2H": (0.09, 0.15, 0.31, 0.52),
           "C3L": (0.10, 0.14, 0.21, 0.35), "C3M": (0.09, 0.14, 0.25, 0.41), "C3H": (0.08, 0.13, 0.27, 0.43)},
}
BETA_PGA = 0.64                 # every curve of Tables 5-39 and 5-40
REFERENCE_SA1_OVER_PGA = 1.5    # of the reference spectrum shape (text before Equation 5-6)
# Table 5-42, degradation factor kappa for short, moderate and long duration.
KAPPA = {("C2", "LC"): (0.60, 0.30, 0.10), ("C2", "PC"): (0.40, 0.20, 0.00),
         ("C3", "LC"): (0.50, 0.30, 0.10), ("C3", "PC"): (0.40, 0.20, 0.00)}
DURATIONS = ("short", "moderate", "long")

# ---------------------------------------------------------------------------------------------------------------------
# Choices where the manual is silent or inconsistent. Approved by the project lead on 2026-11-28.
# ---------------------------------------------------------------------------------------------------------------------
ELASTIC_DAMPING = {"L": 10.0, "M": 8.5, "H": 7.0}      # percent of critical, by height; see choice HB-01
CHOICES = [
    {"id": "HB-01", "topic": "Elastic damping of each building type",
     "choice": "10% for low-rise, 8.5% for mid-rise and 7% for high-rise concrete buildings (C2 and C3).",
     "basis": "The manual says elastic damping depends on the structure type and follows Newmark and Hall, but gives no values. These are the values in the NHERI SimCenter's open capacity-spectrum code (SimCenterBackendApplications, capacitySpectrum/DampingModels.py), which attributes them to Table 3 of Newmark and Hall (1982)."},
    {"id": "HB-02", "topic": "The capacity curve between yield and ultimate",
     "choice": "An arc of an ellipse that leaves the yield point with the elastic slope and reaches the ultimate point with zero slope.",
     "basis": "The manual says only that the curve passes from an elastic to a fully plastic state between the two points. The ellipse is the form given by Cao and Petersen (2006, Bull. Seismol. Soc. Am. 96, Appendix) and used in the SimCenter's code."},
    {"id": "HB-03", "topic": "Area of the hysteresis loop",
     "choice": "The parallelogram through the peak points, with sides at the elastic stiffness and at the tangent stiffness of the capacity curve at the peak.",
     "basis": "The manual defines the area as that of a symmetric push and pull of the capacity curve but gives no formula, and refers to Tokas and Lobo (2008) for the approach in Hazus. This is the formula of Cao and Petersen (2006), as written out by Steelman and Hajjar and in the SimCenter's code."},
    {"id": "HB-04", "topic": "Equation 5-10: hysteretic damping as a percentage",
     "choice": "The term Area / (2 pi D A) is multiplied by 100 before it is added to the elastic damping.",
     "basis": "Equations 5-7 and 5-8 take damping as a percentage: both reduction factors equal 1 at 5. Equation 5-10 as printed adds the fraction Area / (2 pi D A), which cannot exceed 0.64, to a percentage, which would make hysteretic damping and the degradation factors of Table 5-42 immaterial. The SimCenter's code adds the fraction as printed (the line that multiplies by 100 is commented out there), so results will differ from it."},
    {"id": "HB-05", "topic": "Effective damping along the demand spectrum",
     "choice": "Each trial point on the capacity curve is tested against the demand spectrum reduced for that point's own effective damping, which also sets the period at which the acceleration and velocity domains meet (Equation 5-14). Beyond the period TVD the damping is that of the capacity-curve point whose period is TVD.",
     "basis": "Equations 5-11 to 5-14 name the damping at each transition period but the manual does not describe the search for the intersection."},
    {"id": "HB-06", "topic": "Magnitude and duration",
     "choice": "A scenario layer's magnitude sets TVD (Equation 4-4) and the duration (short up to 5.5, long from 7.5, moderate between). A probabilistic layer has no magnitude: TVD is taken as 10 s, as the manual assumes when the magnitude is unknown, and the duration follows the manual's convention by return period (100 and 200 years short; 500 to 1,000 moderate; 1,500 to 2,500 long), a return period between or beyond those taking the nearest. A layer with neither is treated as magnitude 7: TVD 10 s, moderate duration.",
     "basis": "Manual, section 4.1.3.2 and the text after Table 5-42. The rule for return periods the manual does not list, and for layers with no magnitude, is ours."},
    {"id": "HB-07", "topic": "Ground motion at the building",
     "choice": "The short-period and 1-second spectral accelerations of the demand spectrum are the hazard layer's Sa(0.3 s) and Sa(1.0 s) at the building, with no soil factors.",
     "basis": "Decision DMG-03: the layer's values are used as they are, for the site condition the layer states."},
    {"id": "HB-08", "topic": "Method 2: the spectrum shape",
     "choice": "The medians of Tables 5-39 and 5-40 are converted with Equation 5-6, taking the ratio of PGA to 1-second spectral acceleration from the hazard layer's own values at the building, in place of Tables 5-35 and 5-36, and a soil factor of 1.",
     "basis": "The tabulated medians hold for a spectrum whose Sa(1.0 s) is 1.5 times its PGA, at a soil site. The manual provides Equation 5-6 for other shapes, with the ratio looked up from magnitude and distance; a hazard layer gives the ratio directly. The soil factor is 1 for the reason of HB-07. The alternative is to use the tabulated medians unchanged, which suits a soil site in a large earthquake and no other case."},
    {"id": "HB-09", "topic": "Constants in the period and displacement formulas",
     "choice": "0.32 and 9.8, as printed in Equations 4-2, 4-3 and 5-15.",
     "basis": "They are rounded forms of the exact values (0.3198 and 9.779 for inches and g). The printed values are kept so that the calculation is the manual's."},
]


# ---------------------------------------------------------------------------------------------------------------------
# The classes and their spectral-displacement curves (Tables 5-21 and 5-22, transcribed and checked earlier)
# ---------------------------------------------------------------------------------------------------------------------
STATUS = "In use. Approved by the project lead on 2026-11-28; open to review."
LISTED_RETURN_PERIODS = {100: "short", 200: "short", 500: "moderate", 750: "moderate", 1000: "moderate", 1500: "long", 2000: "long", 2500: "long"}
DESCRIPTIONS = {"C2": "Concrete shear walls", "C3": "Concrete frame with unreinforced masonry infill walls"}
HEIGHTS = {"L": "low-rise, 1 to 3 stories", "M": "mid-rise, 4 to 7 stories", "H": "high-rise, 8 or more stories"}


def load_classes(path=os.path.join(ROOT, "data", "fragility", "hazus_ndrcb_la_classes.json")):
    """{class label: {'type', 'level', 'sd': ((median in, beta) x 4)}} for the twelve classes, e.g. 'C2L-PC'."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for c in data["classes"]:
        typ, lvl = c["class"].split("-")
        sd = c["spectral_displacement_in"]
        out[c["class"]] = {"type": typ, "level": lvl,
                           "sd": tuple((sd[s]["median"], sd[s]["beta"]) for s in ("slight", "moderate", "extensive", "complete"))}
    return out


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def in_order(curves):
    """The four chances of reaching each state or worse, with a worse state never more likely than a milder one.
    The curves of a class have different betas and can cross at low demand (as for the bridges, decision DMG-04)."""
    ex = list(curves)
    for i in range(1, 4):
        ex[i] = min(ex[i], ex[i - 1])
    return ex


def state_probabilities(exceedance):
    """Probabilities of the five states from the four ordered chances of reaching each state or worse."""
    ex = exceedance
    return [1.0 - ex[0], ex[0] - ex[1], ex[1] - ex[2], ex[2] - ex[3], ex[3]]


# ---------------------------------------------------------------------------------------------------------------------
# Method 1: capacity spectrum
# ---------------------------------------------------------------------------------------------------------------------
def t_vd(magnitude):
    """Equation 4-4:  TVD = 1/fc = 10 ^ [(M - 5) / 2], in seconds."""
    return 10.0 ** ((magnitude - 5.0) / 2.0)


def duration_for_magnitude(magnitude):
    """Text after Table 5-42: short for M of 5.5 or less, long for M of 7.5 or more, moderate otherwise."""
    return "short" if magnitude <= 5.5 else "long" if magnitude >= 7.5 else "moderate"


def duration_for_return_period(years):
    """The manual's convention: 100 and 200 years short; 500, 750 and 1,000 moderate; 1,500, 2,000 and 2,500 long.
    A return period it does not list takes the duration of the nearest listed one (choice HB-06)."""
    return LISTED_RETURN_PERIODS[min(LISTED_RETURN_PERIODS, key=lambda y: (abs(y - years), y))]


def timing(layer, level):
    """TVD (s), the duration and the reason, for a hazard layer and one of its levels (choice HB-06).
    A scenario made by SR-HazardMaker records its magnitude under source.scenario, a USGS ShakeMap under source.event;
    a level of a probabilistic layer records its return period."""
    src = layer.get("source") or {}
    for key in ("scenario", "event"):
        m = (src.get(key) or {}).get("magnitude")
        if isinstance(m, (int, float)) and not isinstance(m, bool):
            return {"tvd": t_vd(m), "duration": duration_for_magnitude(m), "basis": f"magnitude {m:g}"}
    rp = level.get("return_period_years")
    if isinstance(rp, (int, float)) and not isinstance(rp, bool):
        return {"tvd": 10.0, "duration": duration_for_return_period(rp), "basis": f"return period of {rp:g} years"}
    return {"tvd": 10.0, "duration": "moderate", "basis": "no magnitude recorded, taken as 7"}


def reduction_factors(b_eff):
    """Equations 5-7 and 5-8, with damping as a percentage:
         RA = 2.12 / (3.21 - 0.68 ln(Beff))        RV = 1.65 / (2.31 - 0.41 ln(Beff))"""
    return 2.12 / (3.21 - 0.68 * math.log(b_eff)), 1.65 / (2.31 - 0.41 * math.log(b_eff))


class Capacity:
    """A capacity curve: straight to the yield point, an arc of an ellipse to the ultimate point, flat beyond (HB-02)."""

    def __init__(self, dy, ay, du, au):
        self.dy, self.ay, self.du, self.au = dy, ay, du, au
        self.ke = ay / dy                                                    # elastic stiffness, g per inch
        self.ax = (au * au * dy - ay * ay * du) / (2 * au * dy - ay * dy - ay * du)
        self.b = au - self.ax
        self.c = math.sqrt(dy * self.b * self.b * (du - dy) / (ay * (ay - self.ax)))

    def a(self, d):
        """Spectral acceleration (g) at spectral displacement d (in)."""
        if d <= self.dy:
            return self.ke * d
        if d >= self.du:
            return self.au
        return self.ax + self.b * math.sqrt(max(0.0, 1.0 - ((d - self.du) / self.c) * ((d - self.du) / self.c)))

    def tangent(self, d):
        """Slope of the curve at d, g per inch."""
        if d <= self.dy:
            return self.ke
        if d >= self.du:
            return 0.0
        return (self.b / self.c) * (self.b / self.c) * (self.du - d) / (self.a(d) - self.ax)

    def period(self, d):
        """Equation 4-2:  T = 0.32 sqrt(SD / SA), with SD in inches and SA in g."""
        return 0.32 * math.sqrt(d / self.a(d))

    def loop_area(self, d):
        """Area of the hysteresis loop of a push and pull to +d and -d (HB-03)."""
        a, kt = self.a(d), self.tangent(d)
        if d <= self.dy or kt >= self.ke:
            return 0.0
        return max(0.0, 4.0 * (a - d * self.ke) * (d * kt - a) / (self.ke - kt))

    def effective_damping(self, d, b_elastic, kappa, as_percentage=True):
        """Equation 5-10:  Beff = BE + kappa * ( Area / (2 pi D A) ), the bracket taken as a percentage (HB-04)."""
        if d <= 0:
            return b_elastic
        hysteretic = self.loop_area(d) / (2.0 * math.pi * d * self.a(d))
        return b_elastic + kappa * hysteretic * 100.0 if as_percentage else b_elastic + kappa * hysteretic


def performance_point(capacity, sas, sa1, tvd, b_elastic, kappa, as_percentage=True):
    """Where the capacity curve meets the demand spectrum reduced for effective damping (Equations 5-11 to 5-15).

    sas, sa1: 5%-damped spectral acceleration at short period and at 1 second, in g.  Returns a dict with the peak
    spectral displacement d (in), acceleration a (g), effective damping (%), and period (s)."""
    if sas <= 0 or sa1 <= 0:
        return {"d": 0.0, "a": 0.0, "b_eff": b_elastic, "period": capacity.period(capacity.dy)}
    tav = sa1 / sas                                  # where constant acceleration meets constant velocity (section 4.1.3.2)
    te = capacity.period(capacity.dy)
    if tvd <= te:                                    # damping at the capacity-curve point whose period is TVD (HB-05)
        b_tvd = b_elastic
    else:
        lo, hi = capacity.dy, capacity.du
        while capacity.period(hi) < tvd:
            hi *= 2.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if capacity.period(mid) < tvd:
                lo = mid
            else:
                hi = mid
        b_tvd = capacity.effective_damping(0.5 * (lo + hi), b_elastic, kappa, as_percentage)

    def demand(d):
        t = capacity.period(d)
        b = capacity.effective_damping(d, b_elastic, kappa, as_percentage)
        ra, rv = reduction_factors(b)
        tavb = tav * ra / rv                         # Equation 5-14:  TAVB = TAVi * RA[B] / RV[B]
        if t <= tavb:
            return sas / ra                          # Equation 5-11:  SA[T] = SASi / RA[Beff]
        if t <= tvd:
            return sa1 / t / rv                      # Equation 5-12:  SA[T] = (SA1i / T) / RV[Beff]
        return sa1 * tvd / (t * t) / reduction_factors(b_tvd)[1]      # Equation 5-13:  SA[T] = (SA1i * TVD / T^2) / RV[BTVD]

    gap = lambda d: demand(d) - capacity.a(d)        # positive while the demand exceeds the capacity
    lo, hi = 1e-9, capacity.du
    while gap(hi) > 0:
        hi *= 2.0
        if hi > 1e6:
            raise ValueError("no intersection of capacity and demand")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if gap(mid) > 0:
            lo = mid
        else:
            hi = mid
    d = 0.5 * (lo + hi)
    return {"d": d, "a": capacity.a(d), "b_eff": capacity.effective_damping(d, b_elastic, kappa, as_percentage), "period": capacity.period(d)}


def method1(cls, sas, sa1, magnitude=None, return_period=None, classes=None, as_percentage=True, when=None):
    """Damage-state probabilities of one class by the capacity-spectrum method.

    Give the scenario's magnitude, or the return period of a probabilistic layer, or neither (choice HB-06); or give
    `when`, the result of timing() for a hazard layer."""
    c = (classes or load_classes())[cls]
    if when is not None:
        tvd, dur = when["tvd"], when["duration"]
    elif magnitude is not None:
        tvd, dur = t_vd(magnitude), duration_for_magnitude(magnitude)
    elif return_period is not None:
        tvd, dur = 10.0, duration_for_return_period(return_period)
    else:
        tvd, dur = 10.0, "moderate"
    kappa = KAPPA[(c["type"][:2], c["level"])][DURATIONS.index(dur)]
    b_e = ELASTIC_DAMPING[c["type"][2]]
    pp = performance_point(Capacity(*CAPACITY[c["type"]]), sas, sa1, tvd, b_e, kappa, as_percentage)
    curves = [phi(math.log(pp["d"] / med) / beta) if pp["d"] > 0 else 0.0 for med, beta in c["sd"]]   # Equation 5-3
    ex = in_order(curves)
    return dict(pp, tvd=tvd, duration=dur, kappa=kappa, b_elastic=b_e, curves=curves, exceedance=ex, p=state_probabilities(ex))


# ---------------------------------------------------------------------------------------------------------------------
# Method 2: equivalent PGA
# ---------------------------------------------------------------------------------------------------------------------
def method2(cls, pga, sa1=None, adjust=True, classes=None):
    """Damage-state probabilities of one class from the equivalent-PGA curves.

    adjust=True converts the tabulated medians with Equation 5-6,
         PGAds = PGA(R,ds) * R(PGA/SA1) * (1.5 / FV),
    taking the ratio R from the layer's own pga and sa1 at the building and FV = 1 (choice HB-08).
    adjust=False uses the tabulated medians unchanged."""
    c = (classes or load_classes())[cls]
    medians = list(EQUIVALENT_PGA[c["level"]][c["type"]])
    ratio = None
    if adjust:
        if sa1 is None or sa1 <= 0 or pga <= 0:
            return {"medians": [None] * 4, "ratio": None, "exceedance": [0.0] * 4, "p": [1.0, 0.0, 0.0, 0.0, 0.0]}
        ratio = pga / sa1
        medians = [m * ratio * REFERENCE_SA1_OVER_PGA for m in medians]
    ex = in_order([phi(math.log(pga / m) / BETA_PGA) if pga > 0 else 0.0 for m in medians])
    return {"medians": medians, "ratio": ratio, "exceedance": ex, "p": state_probabilities(ex)}


# ---------------------------------------------------------------------------------------------------------------------
# Self-test: the tables are consistent, the equations behave as the manual says, the pieces fit together
# ---------------------------------------------------------------------------------------------------------------------
def self_test():
    classes = load_classes()
    assert sorted(classes) == sorted(f"{t}-{lv}" for t in TYPES for lv in LEVELS), sorted(classes)
    # damping reduction: both factors are 1 at the 5% of the input spectrum (to the rounding of the printed constants)
    ra, rv = reduction_factors(5.0)
    assert abs(ra - 1) < 0.003 and abs(rv - 1) < 0.003, (ra, rv)
    assert t_vd(7.0) == 10.0 and abs(t_vd(5.0) - 1.0) < 1e-12
    assert [duration_for_magnitude(m) for m in (5.0, 5.5, 5.6, 7.0, 7.4, 7.5, 8.0)] == ["short", "short", "moderate", "moderate", "moderate", "long", "long"]
    assert [duration_for_return_period(y) for y in (100, 200, 475, 500, 975, 1000, 2475, 2500, 10000)] == ["short", "short", "moderate", "moderate", "moderate", "moderate", "long", "long", "long"]
    for typ, (dy, ay, du, au) in CAPACITY.items():
        cap = Capacity(dy, ay, du, au)
        assert dy < du and ay < au
        assert abs(cap.a(dy) - ay) < 1e-12 and abs(cap.a(du) - au) < 1e-12                       # through both control points
        eps = 1e-7
        assert abs((cap.a(dy + eps) - cap.a(dy)) / eps - cap.ke) < 1e-4 * cap.ke                 # leaves yield at the elastic slope
        assert abs(cap.tangent(du - 1e-9)) < 1e-6 and cap.tangent(du + 1) == 0                   # reaches ultimate flat
        grid = [dy + (du - dy) * i / 400 for i in range(401)]
        assert all(cap.a(x) <= cap.a(y) + 1e-15 for x, y in zip(grid, grid[1:]))                 # never falls
        assert all(abs((cap.a(x + eps) - cap.a(x - eps)) / (2 * eps) - cap.tangent(x)) < 1e-5 for x in grid[1:-1])
        assert cap.loop_area(dy) == 0 and cap.loop_area(0.5 * dy) == 0
        assert abs(cap.loop_area(2 * du) - 4 * au * (2 * du - au / cap.ke)) < 1e-12              # elastic-plastic loop past ultimate
        assert cap.effective_damping(dy, 7.0, 0.5) == 7.0
        assert cap.effective_damping(3 * du, 7.0, 1.0) < 7.0 + 100 * 2 / math.pi                 # under the limit of a full plastic loop
    for lvl in LEVELS:
        for typ in TYPES:
            m = EQUIVALENT_PGA[lvl][typ]
            assert all(a < b for a, b in zip(m, m[1:])), (lvl, typ)
            assert all(lc >= pc for lc, pc in zip(EQUIVALENT_PGA["LC"][typ], EQUIVALENT_PGA["PC"][typ]))
    for k in KAPPA.values():
        assert k[0] >= k[1] >= k[2] >= 0
    n = 0
    for cls in classes:
        # Method 2: at the reference shape, Equation 5-6 gives back the tabulated medians
        r = method2(cls, 0.4, sa1=0.4 * REFERENCE_SA1_OVER_PGA, classes=classes)
        t = method2(cls, 0.4, adjust=False, classes=classes)
        assert all(abs(a - b) < 1e-12 for a, b in zip(r["medians"], t["medians"])) and all(abs(a - b) < 1e-12 for a, b in zip(r["p"], t["p"]))
        assert method2(cls, 0.0, sa1=0.0, classes=classes)["p"] == [1.0, 0.0, 0.0, 0.0, 0.0]
        # Method 1: the point found lies on both curves; more shaking never gives less displacement; the extremes are right
        assert method1(cls, 0.0, 0.0, classes=classes)["p"] == [1.0, 0.0, 0.0, 0.0, 0.0]
        last = 0.0
        for scale in (0.02, 0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2):
            for kw in ({"magnitude": 5.0}, {"magnitude": 6.5}, {"magnitude": 7.8}, {"return_period": 475}, {}):
                res = method1(cls, 2.2 * scale, 1.0 * scale, classes=classes, **kw)
                assert res["d"] > 0 and abs(sum(res["p"]) - 1) < 1e-12 and all(-1e-12 <= p <= 1 + 1e-12 for p in res["p"])
                assert all(a >= b - 1e-12 for a, b in zip(res["exceedance"], res["exceedance"][1:]))
                n += 1
            res = method1(cls, 2.2 * scale, 1.0 * scale, magnitude=7.0, classes=classes)
            assert res["d"] >= last - 1e-9, (cls, scale)
            last = res["d"]
        assert method1(cls, 60.0, 40.0, magnitude=7.0, classes=classes)["p"][4] > 0.99
        assert method2(cls, 30.0, sa1=45.0, classes=classes)["p"][4] > 0.99
    return n


def fragility_set():
    """What the dashboard needs to repeat the calculation, with where each part comes from."""
    classes = load_classes()
    out = {}
    for label in sorted(classes, key=lambda k: (TYPES.index(classes[k]["type"]), list(LEVELS).index(classes[k]["level"]))):
        c = classes[label]
        typ, lvl = c["type"], c["level"]
        out[label] = {"type": typ, "level": lvl, "design_level": LEVELS[lvl],
                      "description": f"{DESCRIPTIONS[typ[:2]]}, {HEIGHTS[typ[2]]}, {LEVELS[lvl]}",
                      "capacity": list(CAPACITY[typ]), "elastic_damping": ELASTIC_DAMPING[typ[2]],
                      "kappa": dict(zip(DURATIONS, KAPPA[(typ[:2], lvl)])),
                      "sd": [list(x) for x in c["sd"]], "pga": list(EQUIVALENT_PGA[lvl][typ])}
    return {
        "id": "hazus-concrete-buildings",
        "name": "Hazus concrete buildings: shear wall (C2) and frame with masonry infill (C3), Low-Code and Pre-Code",
        "source": "FEMA, Hazus Earthquake Model Technical Manual, Hazus 6.1, July 2024: sections 4.1.3.2, 5.4.1 to 5.4.3 and 5.6.1; Tables 5-14, 5-15, 5-21, 5-22, 5-39, 5-40 and 5-42; Equations 4-2 to 4-4, 5-3 and 5-6 to 5-15",
        "source_url": "https://www.fema.gov/sites/default/files/documents/fema_hazus-earthquake-model-technical-manual-6-1.pdf",
        "implemented_by": "E. Taciroglu, in tools/hazus_buildings.py of ShakeReady. Where the manual is silent, the capacity-spectrum method follows Cao and Petersen (2006, Bulletin of the Seismological Society of America 96, 365-376) as implemented in the NHERI SimCenter's open code; see the decisions.",
        "applies_to": "latimes-concrete",
        "class_field": "hazus_fragility_class",
        "classes_assigned_by": "A. Nigdelioglu, Z. Tuna Deger and E. Taciroglu (data/la_ndrcb_hazus_fragility.csv)",
        "damage_states": list(STATES),
        "methods": {
            "hazus-capacity-spectrum": {
                "title": "Hazus Method 1: capacity spectrum",
                "summary": "The class's capacity curve is intersected with the demand spectrum built from Sa(0.3 s) and Sa(1.0 s) at the building and reduced for the damping the building develops. The damage-state probabilities are read from the class's lognormal curves on peak spectral displacement.",
                "measures": ["SA0P3", "SA1P0"], "decisions": ["HB-01", "HB-02", "HB-03", "HB-04", "HB-05", "HB-06", "HB-07", "HB-09"]},
            "hazus-equivalent-pga": {
                "title": "Hazus Method 2: equivalent PGA",
                "summary": "Lognormal curves on peak ground acceleration with dispersion 0.64, their medians converted with Equation 5-6 to the spectrum shape at the building.",
                "caution": "The manual gives these curves as guidance for buildings of utility and transportation systems and says Hazus itself does not currently use them.",
                "measures": ["PGA", "SA1P0"], "decisions": ["HB-07", "HB-08"]}},
        "beta_pga": BETA_PGA, "reference_sa1_over_pga": REFERENCE_SA1_OVER_PGA,
        "durations": list(DURATIONS), "listed_return_periods": {str(k): v for k, v in LISTED_RETURN_PERIODS.items()},
        "units": {"capacity": "yield displacement (in), yield acceleration (g), ultimate displacement (in), ultimate acceleration (g)", "elastic_damping": "percent of critical",
                  "sd": "median (in) and lognormal standard deviation of peak spectral displacement, for slight, moderate, extensive and complete damage", "pga": "median equivalent PGA (g) for the same four states, for the reference spectrum shape"},
        "transcription": "The rows of Tables 5-14, 5-15, 5-39, 5-40 and 5-42 for the six building types were read from the manual's text by script and compared with images of the pages; Tables 5-21 and 5-22 likewise, earlier. The equations are images in the manual and were read by eye from the rendered pages.",
        "verification": "A self-test in tools/hazus_buildings.py checks the tables for consistency, that the capacity curve passes through its control points with the right slopes, that both damping reduction factors equal 1 at 5% damping, that Equation 5-6 returns the tabulated medians at the reference spectrum shape, and that the point found lies on both curves. The manual has no worked example for buildings to reproduce.",
        "decisions": [dict(c, status=STATUS) for c in CHOICES],
        "classes": out,
    }


if __name__ == "__main__":
    n = self_test()
    print(f"self-test passed: 12 classes, 6 capacity curves, {n} capacity-spectrum cases")
    target = os.path.join(ROOT, "data", "fragility", "hazus_concrete_buildings.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(fragility_set(), f, indent=1, ensure_ascii=False)
    print("wrote data/fragility/hazus_concrete_buildings.json")
    classes = load_classes()
    print("\nAn illustration only (PGA 0.40 g, Sa(0.3 s) 0.90 g, Sa(1.0 s) 0.35 g, magnitude 7):")
    print(f"{'class':8} {'method 1: Sd in':>16} {'Beff %':>7} {'T s':>5}   {'P(extensive or worse)':>21}   | method 2, converted: {'P(ext+)':>7} | as tabulated: {'P(ext+)':>7}")
    for cls in sorted(classes):
        a = method1(cls, 0.90, 0.35, magnitude=7.0, classes=classes)
        b = method2(cls, 0.40, sa1=0.35, classes=classes)
        c = method2(cls, 0.40, adjust=False, classes=classes)
        print(f"{cls:8} {a['d']:16.3f} {a['b_eff']:7.1f} {a['period']:5.2f}   {a['exceedance'][2]:21.3f}   | {b['exceedance'][2]:28.3f} | {c['exceedance'][2]:21.3f}")
