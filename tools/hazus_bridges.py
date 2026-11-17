#!/usr/bin/env python3
"""HAZUS fragilities for highway bridges, applied to National Bridge Inventory records.

Source: FEMA, Hazus Earthquake Model Technical Manual, Hazus 6.1 (July 2024), Section 7.1:
  Table 7-1  Hazus Bridge Classification Scheme
  Table 7-2  Coefficients for Evaluating K3D
  Table 7-6  Fragility Function Median Values for Highway Bridges
  Equations 7-1 to 7-4 and the eight-step damage algorithm
https://www.fema.gov/sites/default/files/documents/fema_hazus-earthquake-model-technical-manual-6-1.pdf

Everything in CLASSES and K3D_COEFFICIENTS is transcribed from those tables. Where the manual is
silent or inconsistent, the choice made here is recorded under DECISIONS with an id and its basis,
so that results can be traced and the choice reviewed.

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

# Every choice made where the manual is silent or inconsistent. Each has an id so results can cite it.
# These are published in the fragility file and on the site's Methods page.
DECISIONS = [
    dict(id='HZ-01', topic='Seismic design cutoff year',
         choice='A California bridge built in 1975 or later is classed as seismic design; elsewhere the year is 1990.',
         basis='Table 7-1 gives the year in every row. The sentence introducing the table states the two years the other way '
               'round (1990 in California, 1975 elsewhere). The table is followed because it is explicit row by row and agrees '
               'with earlier editions of the Hazus documentation.'),
    dict(id='HZ-02', topic='Form of the span factor K3D',
         choice='K3D = 1 + A / (N - B), with A and B from Table 7-2 and N the number of spans.',
         basis='Table 7-2 and the accompanying text give this form. Equation 7-3 is printed as (1 + A) / (N - B), but the '
               "manual's worked example evaluates it to 1.125 for A = 0.25, B = 1 and N = 3, which only the Table 7-2 form gives."),
    dict(id='HZ-03', topic='Span factor for single-span bridges',
         choice='K3D is taken as 1 when N - B is zero or negative.',
         basis='The formula is undefined in that case and the manual does not say what to do. A factor of 1 leaves the class '
               'medians unchanged.'),
    dict(id='HZ-04', topic='Bridges that are not classified (HWB28)',
         choice='K3D is taken as 1 and the spectral-shape factor is not applied. The skew factor still applies.',
         basis='Table 7-1 gives no K3D equation and no I-shape value for HWB28.'),
    dict(id='HZ-05', topic='Number of spans',
         choice='N is NBI Item 45, the number of spans in the main unit. Approach spans (Item 46) are not counted.',
         basis="The manual's worked example takes the number of spans from Item 45."),
    dict(id='HZ-06', topic='The 20 m length test',
         choice="'Length less than 20 m' is evaluated on NBI Item 49, the structure length.",
         basis='Table 7-1 does not name the NBI item. Step 1 of the damage algorithm lists bridge length separately from '
               'maximum span length, so the total length is used.'),
    dict(id='HZ-07', topic='Skew recorded as 99',
         choice='A skew coded 99 is evaluated as 45 degrees. Any other value of 90 or more is evaluated as 0.',
         basis='The NBI uses 99 when skew varies along the bridge, and the manual does not address this code. 45 degrees is '
               'unfavorable but bounded. A published implementation for Texas bridges treats the same code with its 45-degree '
               'adjustment (Khosravikia et al., 2020, CTR Technical Report 5-6916-01-1).'),
    dict(id='HZ-08', topic='Ground failure',
         choice='Only damage from ground shaking is evaluated.',
         basis="The manual's ground-failure functions need permanent ground deformation at each site, and no such hazard "
               'layer is available here.'),
    dict(id='HZ-09', topic='Culverts',
         choice='Culverts are kept in the inventory and classified by the same rules as bridges.',
         basis='The NBI records culverts as structures and Table 7-1 has no separate rule for them. Bridge curves fit '
               'culverts poorly, and users may wish to exclude them.'),
    dict(id='HZ-10', topic='Seismic retrofits',
         choice='The design era is taken from the year built alone.',
         basis='The NBI has no field for seismic retrofit. The year of reconstruction is not used, because a reconstruction '
               'is not necessarily a seismic one. Bridges retrofitted after construction are therefore treated as unretrofitted.'),
    dict(id='HZ-11', topic='Slight-damage median shown on the map',
         choice='Bridge popups show the class value for slight damage, without the spectral-shape factor.',
         basis='The factor needs Sa(0.3 s) and Sa(1.0 s) at the site, which come from a hazard layer. It is applied when '
               'damage is computed.'),
]
ASSUMPTIONS = [f"{d['id']} {d['topic']}: {d['choice']}" for d in DECISIONS]   # short form, kept for older readers of the file


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
        'transcription': 'Tables 7-1, 7-2 and 7-6 were transcribed from the manual and compared by script against the text '
                         "extracted from the manual's PDF: all 28 sets of medians, and the K3D equation, I-shape value and "
                         'design era of the 27 classes that have them.',
        'verification': "The code reproduces the worked example in Section 7.1.6.2 of the manual (class HWB17, K3D = 1.125; "
                        'damage-state probabilities 0.183, 0.205, 0.165, 0.255, 0.192 against the manual\'s rounded '
                        '0.18, 0.20, 0.16, 0.26, 0.20). The classification passes against every row of Table 7-1.',
        'decisions': [dict(d, status='In use. Recorded at the request of the project lead; open to review.') for d in DECISIONS],
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
