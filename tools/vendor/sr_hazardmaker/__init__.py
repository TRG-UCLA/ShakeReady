"""SR-HazardMaker: turn ground-motion data into hazard layers for the ShakeReady map.

Copyright (c) 2026, E. Taciroglu. Free to use under the BSD 3-Clause license (see LICENSE).
If you use it, please cite it: run `sr-hazardmaker cite`.
"""
# SPDX-License-Identifier: BSD-3-Clause
__version__ = "0.3.3"
__author__ = "E. Taciroglu"
__year__ = "2026"
__license__ = "BSD-3-Clause"
__url__ = "https://github.com/TRG-UCLA/SR-HazardMaker"
__doi__ = "10.5281/zenodo.24356049"          # for all versions; each release also has its own, listed on the Zenodo record


def citation():
    """How to cite SR-HazardMaker: {'text': ..., 'bibtex': ...}. The browser app gives the same."""
    where = "https://doi.org/" + __doi__ if __doi__ else __url__
    text = f"Taciroglu, E. ({__year__}). SR-HazardMaker (Version {__version__}) [Computer software]. {where}"
    lines = ["@software{taciroglu_sr_hazardmaker,", "  author  = {Taciroglu, E.},", "  title   = {{SR-HazardMaker}},",
             f"  year    = {{{__year__}}},", f"  version = {{{__version__}}},"]
    if __doi__:
        lines.append(f"  doi     = {{{__doi__}}},")
    lines += [f"  url     = {{{__url__}}}", "}"]
    return {"text": text, "bibtex": "\n".join(lines)}
