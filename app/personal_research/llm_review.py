"""Offline structured review import; sending filing text externally is disabled."""
from __future__ import annotations

import json
from pathlib import Path


def load_local_review(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("ai_reviews"), list):
        raise ValueError("AI review JSON must contain ai_reviews list")
    return data


def external_review(*args, **kwargs):
    raise RuntimeError(
        "External LLM transmission disabled; import an offline reviewed JSON packet")
