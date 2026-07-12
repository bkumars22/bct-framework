"""Shared JSON-array extraction for LLM outputs — models sometimes wrap the
requested JSON in markdown fences or a sentence of prose despite instructions
not to. Used by case_synthesizer.py and gap_analyzer.py."""
from __future__ import annotations

import json
import re
from typing import Optional


def extract_json_array(raw: str) -> Optional[list]:
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None
