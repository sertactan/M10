"""Personal AI Research — offline PySide6 page in the existing terminal."""
from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QDate, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QMessageBox,
)

from app.personal_research.pipeline import TARGETS, analyze
from app.personal_research.evidence_store import EvidenceStore
from app.personal_research.report_builder import export_report


def _text(value):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


class PersonalResearchPage(QWidget):
    """Source-open, offline analyses; all buttons perform an action."""

    def __init__(self, evidence_root=None, sidecar=None, parent=None):
        super().__init__(parent)
        self.evidence_root = Path(evidence_root or os.environ.get(
            "M10_PERSONAL_EVIDENCE_ROOT", Path(__file__).resolve().parents[3]))
        self.sidecar = Path(sidecar or os.environ.get(
            "M10_PERSONAL_SIDECAR",
            self.evidence_root / ".personal_research_ai_v1_private/runs.sqlite3"))
        self.packet_path = None
        self.report = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        label = QLabel("PERSONAL AI RESEARCH · Kaynaklı kişisel değerlendirme · Original Verified bağımsızdır · PIT değil")
        label.setWordWrap(True)
        root.addWidget(label)
        bar = QHBoxLayout()
        self.ticker_combo = QComboBox()
        self.ticker_combo.setObjectName("personal_ticker")
        self.ticker_combo.addItems(TARGETS)
        self.ticker_combo.currentTextChanged.connect(self._clear)
        bar.addWidget(QLabel("Hisse"))
        bar.addWidget(self.ticker_combo)
        self.fiscal_combo = QComboBox()
        self.fiscal_combo.addItems(("2025-12-31", "2024-12-31", "2023-12-31"))
        self.ticker_combo.currentTextChanged.connect(
            lambda ticker: self.fiscal_combo.setCurrentText(
                "2025-08-29" if ticker == "PENG" else "2025-12-31"))
        self.fiscal_combo.addItem("2025-08-29")
        self.fiscal_combo.setObjectName("personal_fiscal")
        self.fiscal_combo.currentTextChanged.connect(self._clear)
        bar.addWidget(QLabel("Mali dönem"))
        bar.addWidget(self.fiscal_combo)
        self.packet_text = QLineEdit()
        self.packet_text.setObjectName("personal_packet_path")
        self.packet_text.setReadOnly(True)
        self.packet_text.setPlaceholderText("Yerel kaynak paketi seçilmedi")
        bar.addWidget(self.packet_text, 1)
        self.load_button = QPushButton("Kanıt JSON seç")
        self.load_button.clicked.connect(self.choose_packet)
        bar.addWidget(self.load_button)
        self.run_button = QPushButton("Kişisel analiz")
        self.run_button.setObjectName("personal_run")
        self.run_button.clicked.connect(self.run_analysis)
        bar.addWidget(self.run_button)
        self.export_button = QPushButton("JSON + CSV")
        self.export_button.setObjectName("personal_export")
        self.export_button.clicked.connect(self.export)
        self.export_button.setEnabled(False)
        bar.addWidget(self.export_button)
        root.addLayout(bar)
        self.company_label = QLabel("Hisse seçip kişisel analizi çalıştırın.")
        self.company_label.setWordWrap(True)
        root.addWidget(self.company_label)
        self.status = QLabel("READY · Yerel kanıtlar")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        self.models_table = QTableWidget(0, 4)
        self.models_table.setObjectName("personal_models")
        self.models_table.setHorizontalHeaderLabels(
            ("Model", "Original Verified", "Personal AI-Assessed", "Kanıt / eksikler"))
        self.models_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.models_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.models_table.horizontalHeader().setStretchLastSection(True)
        self.models_table.itemSelectionChanged.connect(self._select_model)
        self.models_table.setMinimumHeight(170)
        root.addWidget(self.models_table)
        splitter = QSplitter(Qt.Vertical)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setObjectName("personal_details")
        self.details.setPlaceholderText("Hesap ve kanıt ayrıntıları")
        splitter.addWidget(self.details)
        self.s13_table = QTableWidget(7, 4)
        self.s13_table.setObjectName("personal_s13")
        self.s13_table.setHorizontalHeaderLabels(
            ("Kategori", "Risk (0/25/50/75/100)", "Durum", "Kaynaklı bulgular"))
        self.s13_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.s13_table.horizontalHeader().setStretchLastSection(True)
        self.s13_table.setMinimumHeight(140)
        splitter.addWidget(self.s13_table)
        self.sources_table = QTableWidget(0, 4)
        self.sources_table.setObjectName("personal_sources")
        self.sources_table.setHorizontalHeaderLabels(
            ("Kaynak / model", "SEC accession", "Exact locator", "SEC bağlantısı"))
        self.sources_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sources_table.horizontalHeader().setStretchLastSection(True)
        self.sources_table.cellDoubleClicked.connect(self.open_source)
        self.sources_table.setMinimumHeight(110)
        splitter.addWidget(self.sources_table)
        root.addWidget(splitter, 1)
        splitter.setSizes((270, 190, 170))

    def _clear(self, *_args):
        self.report = None
        self.export_button.setEnabled(False)
        self.models_table.setRowCount(0)
        self.sources_table.setRowCount(0)
        self.s13_table.setRowCount(0)
        self.details.clear()
        self.status.setText("READY · Önceki şirket verileri temizlendi")

    def choose_packet(self):
        file, _filter = QFileDialog.getOpenFileName(
            self, "Yerel kaynak JSON dosyasını seçin", str(self.evidence_root),
            "JSON (*.json)")
        if file:
            self.packet_path = file
            self.packet_text.setText(file)
            self._clear()

    def run_analysis(self):
        self._clear()
        self.run_button.setEnabled(False)
        self.status.setText("Yerel kaynaklar ve model kapıları denetleniyor...")
        try:
            ticker = self.ticker_combo.currentText()
            report = analyze(ticker, evidence_root=self.evidence_root,
                             packet_path=self.packet_path,
                             fiscal_period=self.fiscal_combo.currentText())
            if report["period_end"] != self.fiscal_combo.currentText():
                # A supplied explicit packet can choose its own fiscal period.
                if self.packet_path:
                    raise ValueError("Seçili mali dönem ile kaynak paketi farklı")
            EvidenceStore(self.sidecar).save(report)
            self.report = report
            self._render(report)
            self.export_button.setEnabled(True)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            self.status.setText(f"KANIT / HESAP HATASI · {exc}")
            self.report = None
        finally:
            self.run_button.setEnabled(True)

    def _render(self, report):
        price = _text(report.get("price"))
        self.company_label.setText(
            f"{report['ticker']} · CIK {report['cik']} · FY {report['period_end']} · "
            f"Fiyat {price} ({report.get('price_time') or 'tarih bilinmiyor'}) · "
            f"Analiz {report['created_at']}")
        baseline = report.get("baseline", {})
        self.status.setText(
            f"Original {baseline.get('score_count', '?')} Research skor korundu · "
            f"{report['input_count']} doğrulanmış girdi · "
            f"{len(report['rejected_sources'])} reddedilen kaynak · "
            f"LLM: kapalı / yerel · Canonical: kapalı")
        self.models_table.setRowCount(0)
        for model, personal in report["models"].items():
            original_key = "S14" if model == "PERSONAL_S14_SCENARIO" else model
            old = report.get("original_models", {}).get(original_key, {})
            old_text = f"{_text(old.get('score'))} / {old.get('acceptance', 'N/A')}"
            personal_text = (f"{_text(personal.get('score'))} · {personal.get('status')}"
                             f" · {personal.get('numeric_result_type', 'UNQUANTIFIABLE')}")
            items = (model, old_text, personal_text,
                     ", ".join(personal.get("missing", [])) or "Bileşen ayrıntısını açın")
            index = self.models_table.rowCount()
            self.models_table.insertRow(index)
            for col, value in enumerate(items):
                self.models_table.setItem(index, col, QTableWidgetItem(str(value)))
        self.models_table.resizeColumnsToContents()
        self._populate_s13(report["models"]["S13"])
        self._populate_sources(report)
        if self.models_table.rowCount():
            self.models_table.selectRow(0)

    def _populate_s13(self, result):
        categories = result.get("components", {}).get("categories", {})
        self.s13_table.setRowCount(7)
        for i, code in enumerate(("AUD", "RPT", "REC", "DIL", "REV", "ACQ", "GOV")):
            data = categories.get(code, {}) if isinstance(categories, dict) else {}
            summary = (f"{data.get('observations', 0)} gözlem · "
                       f"{data.get('verified_findings', 0)} doğrulanmış kaynak konumu")
            values = (code, _text(data.get("risk")), data.get("status", "UNRESOLVED"),
                      summary)
            for col, value in enumerate(values):
                self.s13_table.setItem(i, col, QTableWidgetItem(str(value)))
        self.s13_table.resizeColumnsToContents()

    def _populate_sources(self, report):
        self.sources_table.setRowCount(0)
        refs = list(report.get("rows", []))
        refs.extend(report.get("legacy_diagnostics", {}).get("B_Q", {}).get(
            "source_filings", []))
        for source in refs:
            url = source.get("source_ref")
            if not url:
                continue
            values = (source.get("metric", "SEC filing"), source.get("accession"),
                      source.get("source_locator", "Açılacak tam SEC belge"), url)
            i = self.sources_table.rowCount()
            self.sources_table.insertRow(i)
            for j, value in enumerate(values):
                self.sources_table.setItem(i, j, QTableWidgetItem(_text(value)))
        self.sources_table.resizeColumnsToContents()

    def _select_model(self):
        if self.report is None:
            return
        i = self.models_table.currentRow()
        if i < 0:
            return
        model = list(self.report["models"])[i]
        self.details.setPlainText(json.dumps(self.report["models"][model],
                                              indent=2, ensure_ascii=False))

    def open_source(self, row, _column):
        item = self.sources_table.item(row, 3)
        if item is not None:
            url = QUrl(item.text())
            if url.scheme() == "https" and url.host().lower() in (
                    "www.sec.gov", "sec.gov", "data.sec.gov"):
                QDesktopServices.openUrl(url)

    def export(self):
        if self.report is None:
            self.status.setText("Önce analiz çalıştırın")
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Kişisel raporu kaydet",
            str(self.evidence_root / ".personal_research_ai_v1_private/exports" /
                (self.report["ticker"].lower() + "_personal.json")), "JSON (*.json)")
        if path:
            try:
                j, c = export_report(self.report, Path(path).with_suffix(""))
                self.status.setText(f"Rapor kaydedildi: {j} · {c}")
            except OSError as exc:
                QMessageBox.warning(self, "Dışa aktarım hatası", str(exc))
