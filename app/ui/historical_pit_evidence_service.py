"""Read-only historical PIT / WF9 / Learning V3 evidence summary.

The existence of source rows, 2026-retrospective monthly listings, or issuer
documents is NEVER a canonical/PIT certification. This service has no DB
writes, cloud credentials, network calls, model training or score generation.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re


ROOT_PARTS = ("S153ResearchTerminal", "runtime")
STAGE_RE = re.compile(r"^research_pit_[0-9a-f]{16}$")
QA_SCHEMA = "MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1"
STAGE_SCHEMA = "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1"
SITC_SCHEMA = "MERIDYEN_PHASE25S_SITC_OFFICIAL_ACTION_SOURCE_PAIR_RESEARCH_V1"


@dataclass(frozen=True)
class HistoricalPitView:
    state: str
    period: str
    staging_version: str | None
    member_months: int | None
    membership_rows: int | None
    source_price_rows: int | None
    independently_reconciled_price_rows: int | None
    strong_source_candidates: int | None
    conflicting_source_identity_rows: int | None
    affected_strong_tickers: tuple[str, ...]
    sitc_issuer_actions: int | None
    sitc_real_price_pairs: int | None
    canonical_securities: int | None
    wf9: str
    learning_v3: str
    blockers: tuple[str, ...]


def default_runtime_root() -> Path:
    override = os.getenv("S153_PIT_EVIDENCE_ROOT")
    return (Path(override).expanduser()
            if override else Path(os.getenv("LOCALAPPDATA") or Path.home()) / ROOT_PARTS[0] / ROOT_PARTS[1])


def _safe_json(path: Path, max_bytes: int = 2_000_000) -> dict | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        size = path.stat().st_size
        if size <= 0 or size > max_bytes:
            return None
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, UnicodeError, ValueError):
        return None


def _nonnegative(value):
    return value if type(value) is int and value >= 0 else None


def _unavailable(reason: str) -> HistoricalPitView:
    return HistoricalPitView(
        state="NOT_VERIFIED",
        period="2024-01-01 – 2025-09-30",
        staging_version=None, member_months=None, membership_rows=None,
        source_price_rows=None, independently_reconciled_price_rows=None,
        strong_source_candidates=None, conflicting_source_identity_rows=None,
        affected_strong_tickers=(), sitc_issuer_actions=None,
        sitc_real_price_pairs=None, canonical_securities=None,
        wf9="NO_VERIFIED_EXECUTION", learning_v3="NO_VERIFIED_TRAINING",
        blockers=(reason,),
    )


class HistoricalPitEvidenceService:
    """Local, read-only dashboard adapter. Never infers approval from a file name."""

    def __init__(self, runtime_root: Path | None = None):
        self.runtime_root = runtime_root or default_runtime_root()

    def snapshot(self) -> HistoricalPitView:
        root = self.runtime_root
        stage_root = root / "phase25q" / "staged_datasets"
        if stage_root.is_symlink() or not stage_root.is_dir():
            return _unavailable("Phase25Q research staging manifest not available")
        candidates = sorted(
            (d for d in stage_root.iterdir()
             if d.is_dir() and not d.is_symlink() and STAGE_RE.fullmatch(d.name)),
            key=lambda d: d.name,
        )
        valid = []
        for directory in candidates:
            source = _safe_json(directory / "manifest.json")
            if (source and source.get("schema") == STAGE_SCHEMA
                and source.get("status") == "RESEARCH_ONLY_NOT_CANONICAL_PIT"
                and isinstance(source.get("staging_version"), str)
                and re.fullmatch(r"[0-9a-f]{64}", source["staging_version"])
                and source["staging_version"].startswith(directory.name[13:])
                and source.get("canonical_ready") is False
                and source.get("backtest_eligible_securities") == 0
                and source.get("production_DB_modified") is False
                and source.get("period") == {"start": "2024-01-01", "end": "2025-09-30"}):
                valid.append(source)
        if not valid:
            return _unavailable("No intact, unapproved Phase25Q manifest found")
        stage = valid[-1]
        qa = _safe_json(root / "phase25r" / "staging_readonly_reconciliation.json")
        qa_ok = bool(qa and qa.get("schema") == QA_SCHEMA
                     and qa.get("status") == "21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL"
                     and qa.get("staging_version") == stage["staging_version"]
                     and qa.get("canonical_approved_rows") == 0
                     and qa.get("actual_WF9_executed") is False
                     and qa.get("actual_Learning_V3_executed") is False
                     and qa.get("production_DB_modified") is False)

        sitc = _safe_json(root / "phase25s" / "sitc_official_reverse_split_spinoff_price_diagnostics.json")
        sitc_ok = bool(sitc and sitc.get("schema") == SITC_SCHEMA
                       and sitc.get("status") ==
                       "TWO_SEC_OFFICIAL_SITC_ACTION_EVENTS_DOCUMENTED_SOURCE_PRICES_NOT_CERTIFIED"
                       and sitc.get("research_staging_version") == stage["staging_version"]
                       and sitc.get("issuer_documented_actions") == 2
                       and sitc.get("canonical_eligible_securities") == 0
                       and sitc.get("WF9_executed") is False
                       and sitc.get("Learning_V3_trained") is False)
        blockers = [
            "Aylık üyelik dosyaları 2026'da geriye dönük alındı (günlük PIT değil)",
            "Tarihsel SimFinId–CIK/hisse sınıfı, tüm corporate actions ve delisting doğrulanmadı",
            "Kanonik adjusted-price / SEC available_at ve olgun 252 seans etiketi eksik",
        ]
        if not qa_ok:
            blockers.insert(0, "Faz 25R kaynağa bağlı gerçek staging denetimi eksik / sürüm farklı")
        if not sitc_ok:
            blockers.append("SITC 2024 resmî olaylar için gerçek fiyat çifti çalıştırması onaylanmadı")
        conflict_rows = (_nonnegative(qa.get("conflicting_month_ticker_exchange_identity_rows"))
                         if qa_ok else None)
        return HistoricalPitView(
            state="RESEARCH_ONLY_NOT_CANONICAL",
            period="2024-01-01 – 2025-09-30",
            staging_version=stage["staging_version"],
            member_months=_nonnegative(stage.get("month_end_snapshots")),
            membership_rows=_nonnegative(stage.get("monthly_membership_rows")),
            source_price_rows=_nonnegative(stage.get("source_daily_valid_price_rows")),
            independently_reconciled_price_rows=(
                _nonnegative(qa.get("reconciled_strong_candidate_source_valid_rows"))
                if qa_ok else None),
            strong_source_candidates=(
                _nonnegative(qa.get("reconciled_3557_strong_monthly_price_candidates"))
                if qa_ok else None),
            conflicting_source_identity_rows=conflict_rows,
            affected_strong_tickers=(
                tuple(t for t in qa.get("conflicting_strong_cohort_tickers", [])
                      if isinstance(t, str) and len(t) <= 12)
                if qa_ok else ()),
            sitc_issuer_actions=2 if sitc_ok else None,
            sitc_real_price_pairs=(
                _nonnegative(sitc.get("source_pair_diagnostics_computed"))
                if sitc_ok else None),
            canonical_securities=0,
            wf9="BLOCKED_NO_CANONICAL_PIT",
            learning_v3="BLOCKED_NO_MATURE_PIT_LABELS",
            blockers=tuple(blockers),
        )
