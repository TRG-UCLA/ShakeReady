#!/usr/bin/env python3
"""HAZUS fragilities for highway bridges, applied to National Bridge Inventory records.

Source: FEMA, Hazus Earthquake Model Technical Manual, Hazus 6.1 (July 2024), Section 7.1:
  Table 7-1  Hazus Bridge Classification Scheme
  Table 7-2  Coefficients for Evaluating K3D
  Table 7-6  Fragility Function Median Values for Highway Bridges
  Equations 7-1 to 7-4 and the eight-step damage algorithm
https://www.fema.gov/sites/default/files/documents/fema_hazus-earthquake-model-technical-manual-6-1.pdf

Everything in CLASSES and K3D_COEFFICIENTS is transcribed from those tables. Where the manual is
silent or inconsistent, the choice made here is listed under ASSUMPTIONS, so it can be reviewed.

Run this file directly to check the implementation against the manual's worked example and to
write data/fragility/hazus_highway_bridges.json:

    python3 tools/hazus_bridges.py
"""
import json
import math
import os

DAMAGE_STATES = ['Slight', 'Moderate', 'Extensive', 'Complete']
BETA_SHAKING = 0.6          # dispersion of the ground-shaking fragility functions (Section 7.1.6.2)
BETA_GROUND_FAILURE = 0.2   # dispersion of the ground-failure fragility functions
PGD_MEDIANS_IN = [3.9, 3.9, 3.9, 13.8]   # Table 7-6, identical for all classes; not used by the map yet

# Table 7-2: K3D = 1 + A / (N - B), N = number of spans
K3D_COEFFICIENTS = {
    'EQ1': (0.25, 1), 'EQ2': (0.33, 0), 'EQ3': (0.33, 1), 'EQ4': (0.09, 1),
    'EQ5': (0.05, 0), 'EQ6': (0.20, 1), 'EQ7': (0.10, 0),
}

# Tables 7-1 and 7-6. medians = Sa(1.0 s) in g for Slight, Moderate, Extensive, Complete.
# k3d = which equation of Table 7-2 applies; ishape = whether the Kshape factor applies.
CLASSES = {
    1:  dict(medians=[0.40, 0.50, 0.70, 0.90], k3d='EQ1', ishape=0, design='Conventional', description='Major bridge, maximum span over 150 m'),
    2:  dict(medians=[0.60, 0.90, 1.10, 1.70], k3d='EQ1', ishape=0, design='Seismic',      description='Major bridge, maximum span over 150 m'),
    3:  dict(medians=[0.80, 1.00, 1.20, 1.70], k3d='EQ1', ishape=1, design='Conventional', description='Single span'),
    4:  dict(medians=[0.80, 1.00, 1.20, 1.70], k3d='EQ1', ishape=1, design='Seismic',      description='Single span'),
    5:  dict(medians=[0.25, 0.35, 0.45, 0.70], k3d='EQ1', ishape=0, design='Conventional', description='Multi-column bent, simple support, concrete (outside California)'),
    6:  dict(medians=[0.30, 0.50, 0.60, 0.90], k3d='EQ1', ishape=0, design='Conventional', description='Multi-column bent, simple support, concrete (California)'),
    7:  dict(medians=[0.50, 0.80, 1.10, 1.70], k3d='EQ1', ishape=0, design='Seismic',      description='Multi-column bent, simple support, concrete'),
    8:  dict(medians=[0.35, 0.45, 0.55, 0.80], k3d='EQ2', ishape=0, design='Conventional', description='Single column, box girder, continuous concrete (California)'),
    9:  dict(medians=[0.60, 0.90, 1.30, 1.60], k3d='EQ3', ishape=0, design='Seismic',      description='Single column, box girder, continuous concrete (California)'),
    10: dict(medians=[0.60, 0.90, 1.10, 1.50], k3d='EQ2', ishape=1, design='Conventional', description='Continuous concrete'),
    11: dict(medians=[0.90, 0.90, 1.10, 1.50], k3d='EQ3', ishape=1, design='Seismic',      description='Continuous concrete'),
    12: dict(medians=[0.25, 0.35, 0.45, 0.70], k3d='EQ4', ishape=0, design='Conventional', description='Multi-column bent, simple support, steel (outside California)'),
    13: dict(medians=[0.30, 0.50, 0.60, 0.90], k3d='EQ4', ishape=0, design='Conventional', description='Multi-column bent, simple support, steel (California)'),
    14: dict(medians=[0.50, 0.80, 1.10, 1.70], k3d='EQ1', ishape=0, design='Seismic',      description='Multi-column bent, simple support, steel'),
    15: dict(medians=[0.75, 0.75, 0.75, 1.10], k3d='EQ5', ishape=1, design='Conventional', description='Continuous steel'),
    16: dict(medians=[0.90, 0.90, 1.10, 1.50], k3d='EQ3', ishape=1, design='Seismic',      description='Continuous steel'),
    17: dict(medians=[0.25, 0.35, 0.45, 0.70], k3d='EQ1', ishape=0, design='Conventional', description='Multi-column bent, simple support, prestressed concrete (outside California)'),
    18: dict(medians=[0.30, 0.50, 0.60, 0.90], k3d='EQ1', ishape=0, design='Conventional', description='Multi-column bent, simple support, prestressed concrete (California)'),
    19: dict(medians=[0.50, 0.80, 1.10, 1.70], k3d='EQ1', ishape=0, design='Seismic',      description='Multi-column bent, simple support, prestressed concrete'),
    20: dict(medians=[0.35, 0.45, 0.55, 0.80], k3d='EQ2', ishape=0, design='Conventional', description='Single column, box girder, prestressed continuous concrete (California)'),
    21: dict(medians=[0.60, 0.90, 1.30, 1.60], k3d='EQ3', ishape=0, design='Seismic',      description='Single column, box girder, prestressed continuous concrete (California)'),
    22: dict(medians=[0.60, 0.90, 1.10, 1.50], k3d='EQ2', ishape=1, design='Conventional', description='Continuous concrete (prestressed)'),
    23: dict(medians=[0.90, 0.90, 1.10, 1.50], k3d='EQ3', ishape=1, design='Seismic',      description='Continuous concrete (prestressed)'),
    24: dict(medians=[0.25, 0.35, 0.45, 0.70], k3d='EQ6', ishape=0, design='Conventional', description='Multi-column bent, simple support, steel, under 20 m long (outside California)'),
    25: dict(medians=[0.30, 0.50, 0.60, 0.90], k3d='EQ6', ishape=0, design='Conventional', description='Multi-column bent, simple support, steel, under 20 m long (California)'),
    26: dict(medians=[0.75, 0.75, 0.75, 1.10], k3d='EQ7', ishape=1, design='Conventional', description='Continuous steel, under 20 m long (outside California)'),
    27: dict(medians=[0.75, 0.75, 0.75, 1.10], k3d='EQ7', ishape=1, design='Conventional', description='Continuous steel, under 20 m long (California)'),
    28: dict(medians=[0.80, 1.00, 1.20, 1.70], k3d=None,  ishape=0, design='Not classified', description='All other bridges that are not classified'),
}

ASSUMPTIONS = [
    "Seismic design cutoff: Table 7-1 is followed (1975 in California, 1990 elsewhere). The sentence above the table in the "
    "Hazus 6.1 manual states the two years the other way round; the table matches earlier Hazus documentation.",
    "K3D = 1 + A / (N - B), as given in Table 7-2 and the text. Equation 7-3 is typeset as (1 + A) / (N - B), but the manual's "
    "worked example evaluates it to 1.125 for A = 0.25, B = 1, N = 3, which is the Table 7-2 form.",
    "Where N - B is zero or negative (a single-span bridge with an equation that has B = 1), K3D is taken as 1. The manual does "
    "not say what to do in this case.",
    "HWB28 has no K3D equation or Ishape entry in Table 7-1; K3D is taken as 1 and Kshape is not applied.",
    "Number of spans N is NBI Item 45 (main unit spans), as in the manual's example.",
    "'Length less than 20 m' is evaluated on NBI Item 49 (structure length).",
    "A skew coded 99 in the NBI (skew varies along the bridge) is evaluated as 45 degrees. The manual does not address this "
    "code. A value of 90 or more is otherwise treated as 0.",
    "Only ground shaking is evaluated. Ground-failure (permanent ground deformation) damage needs a displacement hazard layer.",
]


def classify(is_california, year_built, kind, design_type, spans, max_span_m, length_m):
    """Hazus class (1 to 28) from NBI fields, following Table 7-1 from top to bottom.

    kind: NBI Item 43A (1 digit); design_type: NBI Item 43B (2 digits). Together they form the 'NBI class', e.g. 205.
    """
    seismic = year_built >= (1975 if is_california else 1990)
    if max_span_m > 150:
        return 2 if seismic else 1
    if spans == 1:
        return 4 if seismic else 3
    k, t = int(kind), int(design_type)
    if k == 1 and 1 <= t <= 6:                       # 101-106 concrete, simple support
        return 7 if seismic else (6 if is_california else 5)
    if k == 2 and 1 <= t <= 6:                       # 201-206 continuous concrete
        if is_california and t in (5, 6):            # 205-206 box girder, California
            return 9 if seismic else 8
        return 11 if seismic else 10
    if k == 3 and 1 <= t <= 6:                       # 301-306 steel, simple support
        if seismic:
            return 14
        short = length_m < 20
        return (25 if short else 13) if is_california else (24 if short else 12)
    if k == 4 and 2 <= t <= 10:                      # 402-410 continuous steel
        if seismic:
            return 16
        if length_m < 20:
            return 27 if is_california else 26
        return 15
    if k == 5 and 1 <= t <= 6:                       # 501-506 prestressed concrete, simple support
        return 19 if seismic else (18 if is_california else 17)
    if k == 6 and 1 <= t <= 7:                       # 601-607 prestressed continuous concrete
        if is_california and t in (5, 6):            # 605-606 box girder, California
            return 21 if seismic else 20
        return 23 if seismic else 22
    return 28


def effective_skew(skew_deg):
    """Skew angle to use in Equation 7-1 (see ASSUMPTIONS for the NBI code 99)."""
    if skew_deg == 99:
        return 45.0
    if skew_deg < 0 or skew_deg >= 90:
        return 0.0
    return float(skew_deg)


def k_skew(skew_deg):
    """Equation 7-1: Kskew = sqrt(sin(90 - alpha))."""
    return math.sqrt(math.sin(math.radians(90.0 - effective_skew(skew_deg))))


def k_3d(hazus_class, spans):
    """Table 7-2: K3D = 1 + A / (N - B)."""
    eq = CLASSES[hazus_class]['k3d']
    if eq is None:
        return 1.0
    a, b = K3D_COEFFICIENTS[eq]
    return 1.0 + a / (spans - b) if spans - b > 0 else 1.0


def k_shape(sa10, sa03):
    """Equation 7-2: Kshape = 2.5 * Sa(1.0 s) / Sa(0.3 s)."""
    return 2.5 * sa10 / sa03


def adjusted_medians(hazus_class, spans, skew_deg, sa10=None, sa03=None):
    """Step 4: the class medians adjusted for this bridge, in g of Sa(1.0 s).

    Slight is multiplied by min(1, Kshape) when Ishape = 1 (this needs both spectral values);
    Moderate, Extensive and Complete are multiplied by Kskew * K3D.
    """
    c = CLASSES[hazus_class]
    m = list(c['medians'])
    factor_slight = 1.0
    if c['ishape'] == 1 and sa10 is not None and sa03:
        factor_slight = min(1.0, k_shape(sa10, sa03))
    k = k_skew(skew_deg) * k_3d(hazus_class, spans)
    return [m[0] * factor_slight, m[1] * k, m[2] * k, m[3] * k]


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def damage_probabilities(hazus_class, spans, skew_deg, sa10, sa03=None):
    """Step 5: probabilities of None, Slight, Moderate, Extensive, Complete from ground shaking."""
    if sa10 <= 0:
        return [1.0, 0.0, 0.0, 0.0, 0.0]
    med = adjusted_medians(hazus_class, spans, skew_deg, sa10, sa03)
    exceed = [_phi(math.log(sa10 / m) / BETA_SHAKING) for m in med]
    # a fragility curve for a worse state can cross above a milder one when medians are equal or
    # reordered by the adjustments; keep the exceedance probabilities non-increasing
    for i in range(1, 4):
        exceed[i] = min(exceed[i], exceed[i - 1])
    return [1 - exceed[0], exceed[0] - exceed[1], exceed[1] - exceed[2], exceed[2] - exceed[3], exceed[3]]


def fragility_set():
    return {
        'id': 'hazus-highway-bridges',
        'name': 'HAZUS highway bridges',
        'source': 'FEMA, Hazus Earthquake Model Technical Manual, Hazus 6.1, July 2024, Section 7.1 (Tables 7-1, 7-2 and 7-6; Equations 7-1 to 7-4)',
        'source_url': 'https://www.fema.gov/sites/default/files/documents/fema_hazus-earthquake-model-technical-manual-6-1.pdf',
        'applies_to': 'nbi-bridges',
        'intensity_measure': 'SA(1.0)',
        'intensity_measure_also_needed': 'SA(0.3) for the Kshape factor, classes with ishape = 1',
        'units': 'g',
        'distribution': 'lognormal',
        'beta': BETA_SHAKING,
        'damage_states': DAMAGE_STATES,
        'k3d_coefficients': {k: {'A': a, 'B': b} for k, (a, b) in K3D_COEFFICIENTS.items()},
        'adjustments': {
            'k_skew': 'sqrt(sin(90 - skew))',
            'k_3d': '1 + A / (N - B), N = number of spans',
            'k_shape': '2.5 * Sa(1.0) / Sa(0.3)',
            'slight': 'median * min(1, k_shape) if ishape = 1, else median',
            'moderate_extensive_complete': 'median * k_skew * k_3d',
        },
        'assumptions': ASSUMPTIONS,
        'classes': {f'HWB{n}': c for n, c in CLASSES.items()},
    }


def self_test():
    """Reproduce the worked example in Section 7.1.6.2 of the manual.

    A three-span simply supported prestressed concrete bridge near Memphis: built 1968, skew 32 degrees,
    NBI class 501, maximum span 23 m, length 56 m; Sa(1.0 s) = 0.43 g and Sa(0.3 s) = 2.1 g on site class D.
    The manual gives class HWB17, K3D = 1.125, and probabilities 0.18, 0.20, 0.16, 0.26, 0.20.
    """
    cls = classify(False, 1968, 5, 1, 3, 23, 56)
    assert cls == 17, cls
    assert abs(k_3d(17, 3) - 1.125) < 1e-9
    p = damage_probabilities(17, 3, 32, 0.43, 2.1)
    expected = [0.18, 0.20, 0.16, 0.26, 0.20]
    # the manual rounds each exceedance probability to two decimals before differencing
    assert all(abs(a - b) <= 0.015 for a, b in zip(p, expected)), p
    assert abs(sum(p) - 1) < 1e-12
    return cls, k_skew(32), k_3d(17, 3), p, expected


if __name__ == '__main__':
    cls, ks, k3, p, expected = self_test()
    print(f"worked example: class HWB{cls}, Kskew = {ks:.3f}, K3D = {k3:.3f}")
    print("  computed:", ', '.join(f'{v:.3f}' for v in p))
    print("  manual:  ", ', '.join(f'{v:.2f}' for v in expected))
    os.makedirs('data/fragility', exist_ok=True)
    with open('data/fragility/hazus_highway_bridges.json', 'w', encoding='utf-8') as f:
        json.dump(fragility_set(), f, indent=1, ensure_ascii=False)
    print("wrote data/fragility/hazus_highway_bridges.json")
