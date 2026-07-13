"""
Ready-made behavioral contracts for common AI system domains, so a new
user has a real starting point instead of writing always/never/
under_pressure rules from scratch. Each is a JSON file in this directory,
loaded via load_template() / load_all_templates() below.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from ..contract import BehavioralContract

_TEMPLATES_DIR = os.path.dirname(__file__)


def list_template_ids() -> List[str]:
    """Template ids are the JSON filenames without extension, e.g. 'socratic_tutor'."""
    return sorted(
        f[:-5] for f in os.listdir(_TEMPLATES_DIR)
        if f.endswith(".json")
    )


def _load_json(template_id: str) -> Dict:
    path = os.path.join(_TEMPLATES_DIR, f"{template_id}.json")
    if not os.path.exists(path):
        raise ValueError(f"No such template: {template_id!r}. Available: {list_template_ids()}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_template(template_id: str) -> BehavioralContract:
    """Loads one template as a BehavioralContract, e.g. load_template('socratic_tutor')."""
    data = _load_json(template_id)
    return BehavioralContract(
        name=data["name"],
        system=data["system"],
        always=data.get("always", []),
        never=data.get("never", []),
        under_pressure=data.get("under_pressure", []),
        threshold=data.get("threshold", 0.90),
    )


def load_all_templates() -> Dict[str, BehavioralContract]:
    """Returns every template as {template_id: BehavioralContract}."""
    return {tid: load_template(tid) for tid in list_template_ids()}
