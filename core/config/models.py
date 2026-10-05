from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConfig(BaseModel):
    sqlite_path: str
    duckdb_path: str
    parquet_root: str


class ApplicationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_name: str
    market: str = "US"
    database: DatabaseConfig
    strict_pit: bool = True
    allow_mock_data: bool = False


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str
    display_name: str
    enabled: bool
    canonical_formula_version: str
    status: str
    weights: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)
