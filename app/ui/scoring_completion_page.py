"""Offline comparison UI for recovered research formula scores."""
from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit
from app.scoring_completion import load_report

class ScoringCompletionPage(QWidget):
    def __init__(self,report_path:Path,source:Path,phase28:Path,parent=None):
        super().__init__(parent)
        self.report_path,self.source,self.phase28=map(Path,(report_path,source,phase28))
        self.report=None
        root=QVBoxLayout(self)
        self.warning=QLabel('RESEARCH ONLY · Annual fallback formula scores · S14 incomplete · Canonical 0/0 · Estimated activation pending approval')
        self.warning.setWordWrap(True);root.addWidget(self.warning)
        self.status=QLabel('No verified report loaded');self.status.setWordWrap(True);root.addWidget(self.status)
        button=QPushButton('Load verified offline results');button.clicked.connect(self.refresh);root.addWidget(button)
        self.comparison=QTableWidget(0,13)
        self.comparison.setHorizontalHeaderLabels(('Stock','Cached price','Price time','S7','S12',
            'S14','S14 legs','B_Q inputs','S6 inputs','S16-E','S16-C','Features','Full formula scores'))
        self.comparison.setEditTriggers(QTableWidget.NoEditTriggers)
        self.comparison.itemSelectionChanged.connect(self.select_stock)
        self.comparison.setMinimumHeight(210)
        self.comparison.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.comparison)
        self.models=QTableWidget(0,4)
        self.models.setHorizontalHeaderLabels(('Model','Research score','Status','Missing inputs'))
        self.models.setEditTriggers(QTableWidget.NoEditTriggers)
        self.models.itemSelectionChanged.connect(self.select_model)
        self.models.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.models)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);root.addWidget(self.details)
    def refresh(self):
        # Clear first: a bad or changed source must not leave yesterday's scores visible.
        self.report=None;self.comparison.setRowCount(0);self.models.setRowCount(0);self.details.clear()
        try:
            self.report=load_report(self.report_path,self.source,self.phase28)
            for s in self.report['stocks']:
                i=self.comparison.rowCount();self.comparison.insertRow(i)
                s14=next((m['score'] for m in s['models'] if m['model']=='S14'),None)
                present=sum(s['quality'][k]['score'] is not None
                            for k in ('B_Q','S6','S7','S11','S12','S13'))
                v3=s.get('sec_quality_v3') or {}
                values=(s['ticker'],f"{s['price']:.2f} {s['currency']}",s['price_time'],
                        s['quality']['S7']['score'],s['quality']['S12']['score'],s14,
                        f"{present}/6",
                        f"{v3['B_Q_risk_count']}/7" if v3 else 'N/A',
                        f"{v3['S6_partial_count']}/7" if v3 else 'N/A',
                        None,None,len(s['features']),s['full_model_count'])
                for j,v in enumerate(values):
                    self.comparison.setItem(i,j,QTableWidgetItem('N/A' if v is None else f'{v:.2f}' if isinstance(v,float) else str(v)))
            self.status.setText(f"Offline snapshot {self.report['generated_at']} · {self.report['full_model_count']} full research formula scores · prices retain original timestamps; not live")
            self.comparison.resizeColumnsToContents()
            self.comparison.selectRow(0)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            self.report=None;self.comparison.setRowCount(0);self.models.setRowCount(0);self.details.clear()
            self.status.setText('MISSING / INVALID / SOURCE CHANGED · '+str(exc))
    def select_stock(self):
        i=self.comparison.currentRow()
        if not self.report or i<0:return
        stock=self.report['stocks'][i]
        self.models.setRowCount(0)
        for m in stock['models']:
            row=self.models.rowCount();self.models.insertRow(row)
            for j,v in enumerate((m['model'],'N/A' if m['score'] is None else f"{m['score']:.2f}",m['status'],', '.join(m['missing']))):
                self.models.setItem(row,j,QTableWidgetItem(str(v)))
        self.models.resizeColumnsToContents()
        evidence={k:stock[k] for k in ('quality','control_chain','s16_features','daily','features')}
        if stock.get('sec_companyfacts_partial'):
            evidence['sec_companyfacts_partial']=stock['sec_companyfacts_partial']
        if stock.get('sec_quality_v3'):
            evidence['sec_quality_v3']=stock['sec_quality_v3']
        if stock.get('sec_forensic_v3'):
            evidence['sec_forensic_v3']=stock['sec_forensic_v3']
        if stock.get('sec_event_candidates_v3'):
            evidence['sec_event_candidates_v3']=stock['sec_event_candidates_v3']
        if stock.get('sec_jones_v3'):
            evidence['sec_jones_v3']=stock['sec_jones_v3']
        self.details.setPlainText(json.dumps(evidence,ensure_ascii=False,indent=2))
    def select_model(self):
        i,j=self.comparison.currentRow(),self.models.currentRow()
        if self.report and i>=0 and j>=0:
            self.details.setPlainText(json.dumps(self.report['stocks'][i]['models'][j],ensure_ascii=False,indent=2))
