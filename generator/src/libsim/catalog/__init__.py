"""Real book catalogue for the simulator.

Built offline from the Open Library dump (CC0) and calibrated on goodbooks-10k
(CC BY-SA 4.0, aggregates only). Run `libsim catalog build` / `libsim catalog calibrate`;
the results are committed under `libsim/data/`. The helpers below need no polars.
"""

import json
from importlib import resources


def _data(name: str) -> dict:
    return json.loads(resources.files("libsim").joinpath("data", name).read_text(encoding="utf-8"))


def openlibrary_attribution() -> dict:
    source = _data("catalog_meta.json")["source"]
    return {
        "name": "Open Library",
        "license": source["license"],
        "url": source["dataset"],
        "signals_as_of": source["signals_as_of"],
    }


def goodbooks_attribution() -> dict:
    source = _data("calibration.json")["source"]
    return {
        "name": "goodbooks-10k",
        "license": source["license"],
        "url": source["dataset"],
        "attribution": source["attribution"],
    }
