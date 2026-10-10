"""Read-only desktop view for a private Phase25Z experimental report."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path

from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QValueAxis
from PySide6.QtCore import QDateTime, QTimeZone, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

REPORT_SCHEMA = "phase25z_research_backtest_v2"
REQUIRED_RISKS = {"LOOKAHEAD_EX_POST_COHORT", "SURVIVORSHIP_AND_DELISTING",
                  "RETROSPECTIVE_MEMBERSHIP", "CORPORATE_ACTION_PRICE_FACTORS", "SEC_AVAILABLE_AT"}


def default_report_path() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime" / "phase25z" / "research_backtest_v2_desktop.json"


def read_research_report(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 5_000_000:
        raise ValueError("Private V2 report unavailable or too large")
    raw = path.read_bytes()
    obj = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError("Research report must be an object")
    if (obj.get("schema") != REPORT_SCHEMA or obj.get("status") != "EXPERIMENTAL_RESEARCH_ONLY"
            or obj.get("pilot_size") != 25 or len(obj.get("cohort_tickers", [])) != 25
            or obj.get("canonical_accepted_securities") != 0 or obj.get("canonical_accepted_security_dates") != 0
            or obj.get("wf9_status") != "BLOCKED" or obj.get("learning_v3_status") != "NOT_TRAINED"
            or obj.get("research_mode") != "ENABLED_EXPERIMENTAL_ONLY"
            or obj.get("canonical_mode") != "BLOCKED_MISSING_ALL_REQUIRED_EVIDENCE"):
        raise ValueError("Report is not a validated research-only, zero-canonical V2 artifact")
    if (not isinstance(obj.get("risk_ledger"), list)
            or not all(isinstance(r, dict) and isinstance(r.get("detail"), str) for r in obj["risk_ledger"])):
        raise ValueError("Invalid risk ledger")
    risk_codes = {r.get("code") for r in obj["risk_ledger"]}
    d = obj.get("diagnostics", {})
    intervals = d.get("monthly_diagnostics", [])
    if (not REQUIRED_RISKS <= risk_codes or len(intervals) != 20
            or not all("source_adj_index" in r and "source_close_index" in r and "to" in r for r in intervals)
            or not isinstance(obj.get("period"), dict)
            or not all(isinstance(obj["period"].get(k), str) for k in ("start", "end"))
            or len(set(obj["cohort_tickers"])) != 25
            or set(d.get("exact_rebalanced_source_adj_index_contribution", {})) != set(obj["cohort_tickers"])
            or set(d.get("leave_one_out", {})) != set(obj["cohort_tickers"])
            or not isinstance(d.get("largest_single_name_month_moves"), list)
            or not all(isinstance(r.get(k), (int, float)) and math.isfinite(r[k]) for r in intervals for k in ("source_adj_index", "source_close_index"))
            or not isinstance(obj.get("source_price_sha256"), str)
            or len(obj["source_price_sha256"]) != 64):
        raise ValueError("Incomplete V2 graph, contribution or source proof")
    return obj, hashlib.sha256(raw).hexdigest()


def _label(text: str, *, title: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    if title:
        label.setStyleSheet("font-weight: 700; color: #E6C56E; font-size: 16px;")
    return label


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().hide()
    table.horizontalHeader().setStretchLastSection(True)
    return table


class ResearchBacktestPage(QWidget):
    def __init__(self, *, report_path: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.report_path = Path(report_path) if report_path else default_report_path()
        self.loaded_report: dict | None = None
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll)
        body = QWidget()
        layout = QVBoxLayout(body)
        scroll.setWidget(body)
        self.banner = _label("RESEARCH MODE · EXPERIMENTAL ONLY · CANONICAL MODE BLOCKED", title=True)
        layout.addWidget(self.banner)
        self.status = _label("Private V2 report not loaded")
        layout.addWidget(self.status)
        refresh = QPushButton("REFRESH PRIVATE RESEARCH REPORT")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        self.summary = _label("Canonical admissions: 0 · WF9: BLOCKED · Learning V3: NOT_TRAINED")
        layout.addWidget(self.summary)
        self.pilots = _label("Pilot securities: unavailable")
        layout.addWidget(self.pilots)
        self.chart = QChart()
        self.chart.setTitle("Monthly source-price indices · experimental, not OOS")
        self.chart.setBackgroundBrush(QColor("#111B2E"))
        self.chart.setTitleBrush(QColor("#E8EDF6"))
        self.chart.legend().setLabelColor(QColor("#E8EDF6"))
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMinimumHeight(300)
        layout.addWidget(self.chart_view)
        tables = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(_label("All 25 exact adjusted-index contributions", title=True))
        self.contributions = _table(["Pilot ticker", "Signed index contribution", "Leave-one-out index"])
        self.contributions.setMinimumHeight(430)
        self.contributions.setColumnWidth(0, 110)
        self.contributions.setColumnWidth(1, 260)
        left.addWidget(self.contributions)
        tables.addLayout(left, 1)
        right = QVBoxLayout()
        right.addWidget(_label("Largest single-name monthly source moves", title=True))
        self.outliers = _table(["Ticker", "Interval", "Adjusted source move"])
        self.outliers.setMinimumHeight(430)
        self.outliers.setColumnWidth(0, 100)
        self.outliers.setColumnWidth(1, 210)
        right.addWidget(self.outliers)
        tables.addLayout(right, 1)
        layout.addLayout(tables)
        self.source_info = _label("Source and SHA-256: unavailable")
        layout.addWidget(self.source_info)
        self.warnings = _label("Lookahead, survivorship and adjustment evidence required.")
        layout.addWidget(self.warnings)

    def refresh(self) -> None:
        try:
            report, report_hash = read_research_report(self.report_path)
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            self.loaded_report = None
            self.status.setText(f"Research report unavailable: {exc}")
            self.summary.setText("Canonical data unavailable · WF9: BLOCKED · Learning V3: NOT_TRAINED")
            self.contributions.setRowCount(0)
            self.outliers.setRowCount(0)
            self.chart.removeAllSeries()
            return
        self.loaded_report = report
        d = report["diagnostics"]
        self.status.setText(f"25 retrospective pilot securities · {report['period']['start']} to {report['period']['end']}")
        self.summary.setText(
            f"Source Adj. Close index {d['source_adj_index_final']:.4f} · Close index {d['source_close_index_final']:.4f}"
            f"   |   CANONICAL: 0 securities / 0 dates   |   WF9: BLOCKED   |   Learning V3: NOT_TRAINED"
        )
        self.pilots.setText("Pilots: " + ", ".join(report["cohort_tickers"]))
        self._set_chart(report)
        contributions = d["exact_rebalanced_source_adj_index_contribution"]
        ranked = sorted(contributions, key=lambda t: abs(contributions[t]), reverse=True)
        self.contributions.setRowCount(len(ranked))
        for row, ticker in enumerate(ranked):
            for col, value in enumerate((ticker, f"{contributions[ticker]:+.6f}",
                                         f"{d['leave_one_out'][ticker]['index_without']:.4f}")):
                self.contributions.setItem(row, col, QTableWidgetItem(value))
        outliers = d["largest_single_name_month_moves"]
        self.outliers.setRowCount(len(outliers))
        for row, item in enumerate(outliers):
            for col, value in enumerate((item["ticker"], f"{item['from']} → {item['to']}",
                                         f"{item['source_adj_return']:+.4f}")):
                self.outliers.setItem(row, col, QTableWidgetItem(value))
        inputs = report.get("input_sha256", {})
        self.source_info.setText(
            f"Private report: {self.report_path} · SHA-256 {report_hash}\n"
            f"Original source-price SHA-256: {report['source_price_sha256']}\n"
            f"Existing W/X/Y-A/Q report hashes: " + "; ".join(f"{Path(k).name}: {v}" for k, v in inputs.items())
        )
        self.warnings.setText("Research-only limitations: " + " | ".join(
            f"{r['code']} [{r['level']}]: {r['detail']}" for r in report["risk_ledger"]))

    def _set_chart(self, report: dict) -> None:
        self.chart.removeAllSeries()
        for axis in list(self.chart.axes()):
            self.chart.removeAxis(axis)
        d = report["diagnostics"]
        entries = [{"to": report["period"]["start"][:7], "source_adj_index": 1.0,
                    "source_close_index": 1.0}] + d["monthly_diagnostics"]
        values = []
        series = []
        for key, title, color in (("source_adj_index", "Source Adj. Close", "#E6C56E"),
                                  ("source_close_index", "Source Close", "#55B9D3")):
            line = QLineSeries()
            line.setName(title)
            line.setColor(QColor(color))
            for item in entries:
                month = item["to"]
                ts = datetime(int(month[:4]), int(month[5:7]), 1, tzinfo=timezone.utc).timestamp() * 1000
                line.append(ts, float(item[key]))
                values.append(float(item[key]))
            self.chart.addSeries(line)
            series.append(line)
        x = QDateTimeAxis()
        x.setFormat("yyyy-MM")
        x.setTitleText("Source month")
        x.setLabelsColor(QColor("#E8EDF6"))
        y = QValueAxis()
        y.setTitleText("Experimental index (start = 1)")
        y.setLabelsColor(QColor("#E8EDF6"))
        low, high = min(values), max(values)
        y.setRange(max(0.0, low - 0.05), high + 0.05)
        start = datetime.fromisoformat(entries[0]["to"] + "-01").replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(entries[-1]["to"] + "-01").replace(tzinfo=timezone.utc)
        x.setRange(QDateTime.fromSecsSinceEpoch(int(start.timestamp()), QTimeZone.utc()),
                   QDateTime.fromSecsSinceEpoch(int(end.timestamp()), QTimeZone.utc()))
        self.chart.addAxis(x, Qt.AlignBottom)
        self.chart.addAxis(y, Qt.AlignLeft)
        for line in series:
            line.attachAxis(x)
            line.attachAxis(y)
