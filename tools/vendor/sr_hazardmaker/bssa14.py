# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, E. Taciroglu. Part of SR-HazardMaker; see LICENSE.
"""The ground-motion model of Boore, Stewart, Seyhan and Atkinson (2014), "BSSA14".

Boore, D. M., Stewart, J. P., Seyhan, E., and Atkinson, G. M. (2014). NGA-West2 equations for
predicting PGA, PGV, and 5% damped PSA for shallow crustal earthquakes. Earthquake Spectra,
30(3), 1057-1085.

What is implemented: the base model for PGA and for spectral acceleration at 0.3 s and 1.0 s
(the three measures a ShakeReady hazard layer carries), with no regional adjustment to
anelastic attenuation and no basin-depth term. Ground motions are in g, for the RotD50
horizontal component.

The equations are written here from the paper. The coefficient values were taken from the
table in the OpenQuake engine's implementation of the model (openquake/hazardlib/gsim/
boore_2014.py) and the code is tested against that engine's verification tables: see the
tests. docs/scenario.js holds the same model for the browser, tested to agree with this one.
"""
import math

NAME = "Boore, Stewart, Seyhan and Atkinson (2014)"
CITATION = ("Boore, D. M., Stewart, J. P., Seyhan, E., and Atkinson, G. M. (2014). NGA-West2 equations for predicting PGA, PGV, "
            "and 5% damped PSA for shallow crustal earthquakes. Earthquake Spectra, 30(3), 1057-1085.")
MREF, RREF, VREF, F1, F3, V1, V2 = 4.5, 1.0, 760.0, 0.0, 0.1, 225.0, 300.0
MECHANISMS = {"unspecified": "e0", "strike-slip": "e1", "normal": "e2", "reverse": "e3"}
# where the model applies, as stated by its authors
LIMITS = {"magnitude": (3.0, 8.5), "magnitude_normal": (3.0, 7.0), "rjb_km": (0.0, 400.0), "vs30": (150.0, 1500.0)}

COEFFS = {
    "PGA": {"e0": 0.4473, "e1": 0.4856, "e2": 0.2459, "e3": 0.4539, "e4": 1.431, "e5": 0.05053, "e6": -0.1662, "Mh": 5.5, "c1": -1.134, "c2": 0.1917, "c3": -0.008088, "h": 4.5, "Dc3": 0.0, "c": -0.6, "Vc": 1500.0, "f4": -0.15, "f5": -0.00701, "R1": 110.0, "R2": 270.0, "DfR": 0.1, "DfV": 0.07, "phi1": 0.695, "phi2": 0.495, "tau1": 0.398, "tau2": 0.348},
    "SA0P3": {"e0": 1.2217, "e1": 1.2401, "e2": 1.0246, "e3": 1.2653, "e4": 0.95676, "e5": -0.1959, "e6": -0.092855, "Mh": 6.14, "c1": -1.0948, "c2": 0.13388, "c3": -0.005475, "h": 4.93, "Dc3": 0.0, "c": -0.84165, "Vc": 1308.47, "f4": -0.21912, "f5": -0.0067, "R1": 103.15, "R2": 268.59, "DfR": 0.138, "DfV": 0.05, "phi1": 0.675, "phi2": 0.561, "tau1": 0.363, "tau2": 0.229},
    "SA1P0": {"e0": 0.3932, "e1": 0.4218, "e2": 0.207, "e3": 0.4124, "e4": 1.5004, "e5": -0.18983, "e6": 0.17895, "Mh": 6.2, "c1": -1.193, "c2": 0.10248, "c3": -0.00121, "h": 5.74, "Dc3": 0.0, "c": -1.05, "Vc": 1109.95, "f4": -0.10521, "f5": -0.00844, "R1": 116.39, "R2": 270.0, "DfR": 0.098, "DfV": 0.02, "phi1": 0.553, "phi2": 0.625, "tau1": 0.498, "tau2": 0.298}
}


def _event(C, mag, mechanism):
    """Source term: the effect of magnitude and style of faulting."""
    e = C[MECHANISMS[mechanism]]
    if mag <= C["Mh"]:
        return e + C["e4"] * (mag - C["Mh"]) + C["e5"] * (mag - C["Mh"]) * (mag - C["Mh"])
    return e + C["e6"] * (mag - C["Mh"])


def _path(C, mag, rjb):
    """Path term: geometric spreading and anelastic attenuation."""
    r = math.sqrt(rjb * rjb + C["h"] * C["h"])
    return (C["c1"] + C["c2"] * (mag - MREF)) * math.log(r / RREF) + (C["c3"] + C["Dc3"]) * (r - RREF)


def _site(C, vs30, pga_rock):
    """Site term: linear amplification, and the nonlinear part driven by the shaking on rock."""
    f_lin = C["c"] * math.log(min(vs30, C["Vc"]) / VREF)
    f2 = C["f4"] * (math.exp(C["f5"] * (min(vs30, 760.0) - 360.0)) - math.exp(C["f5"] * (760.0 - 360.0)))
    return f_lin + F1 + f2 * math.log((pga_rock + F3) / F3)


def ln_median(measure, mag, mechanism, rjb, vs30):
    """Natural log of the median ground motion in g."""
    Cp = COEFFS["PGA"]
    pga_rock = math.exp(_event(Cp, mag, mechanism) + _path(Cp, mag, rjb))     # median PGA on reference rock, Vs30 = 760 m/s
    C = COEFFS[measure]
    return _event(C, mag, mechanism) + _path(C, mag, rjb) + _site(C, vs30, pga_rock)


def sigma(measure, mag, rjb, vs30):
    """Total standard deviation of the natural log of the ground motion."""
    C = COEFFS[measure]
    if mag <= 4.5:
        tau, phi = C["tau1"], C["phi1"]
    elif mag >= 5.5:
        tau, phi = C["tau2"], C["phi2"]
    else:
        tau = C["tau1"] + (C["tau2"] - C["tau1"]) * (mag - 4.5)
        phi = C["phi1"] + (C["phi2"] - C["phi1"]) * (mag - 4.5)
    if rjb > C["R2"]:
        phi += C["DfR"]
    elif rjb > C["R1"]:
        phi += C["DfR"] * (math.log(rjb / C["R1"]) / math.log(C["R2"] / C["R1"]))
    if vs30 <= V1:
        phi -= C["DfV"]
    elif vs30 < V2:
        phi -= C["DfV"] * (math.log(V2 / vs30) / math.log(V2 / V1))
    return math.sqrt(phi * phi + tau * tau)


def ground_motion(measure, mag, mechanism, rjb, vs30, epsilon=0.0):
    """Ground motion in g: the median, or the median shifted by `epsilon` standard deviations."""
    ln_y = ln_median(measure, mag, mechanism, rjb, vs30)
    if epsilon:
        ln_y += epsilon * sigma(measure, mag, rjb, vs30)
    return math.exp(ln_y)


def check_inputs(mag, mechanism, vs30):
    """Raise ValueError if the inputs fall outside the range the authors give for the model."""
    if mechanism not in MECHANISMS:
        raise ValueError(f"Mechanism must be one of: {', '.join(MECHANISMS)}.")
    lo, hi = LIMITS["magnitude_normal"] if mechanism == "normal" else LIMITS["magnitude"]
    if not (lo <= mag <= hi):
        raise ValueError(f"The model applies to magnitudes {lo} to {hi}" + (" for normal faulting" if mechanism == "normal" else "") + f"; {mag} is outside that.")
    if not (LIMITS["vs30"][0] <= vs30 <= LIMITS["vs30"][1]):
        raise ValueError(f"The model applies to Vs30 from {LIMITS['vs30'][0]:.0f} to {LIMITS['vs30'][1]:.0f} m/s; {vs30} is outside that.")
