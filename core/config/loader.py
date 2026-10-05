from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def load_yaml(path: str | Path, model: type[T]) -> T:
    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    return model.model_validate(data)


def config_hash(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    return hashlib.sha256(raw).hexdigest()
