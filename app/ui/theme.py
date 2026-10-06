from __future__ import annotations

APP_QSS = """
QMainWindow, QWidget {
    background: #0B1220;
    color: #E8EDF6;
    font-family: "Segoe UI";
    font-size: 13px;
}
QFrame#Header, QFrame#Card {
    background: #111B2E;
    border: 1px solid #263550;
    border-radius: 8px;
}
QLabel#AppTitle {
    color: #E6C56E;
    font-size: 19px;
    font-weight: 700;
}
QLabel#Score {
    color: #E6C56E;
    font-size: 30px;
    font-weight: 700;
}
QLabel#Muted {
    color: #8FA0B8;
}
QPushButton {
    background: #C4A24D;
    color: #09111F;
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 700;
}
QPushButton:hover { background: #D6B65C; }
QLineEdit, QComboBox, QDateEdit {
    background: #0D1728;
    border: 1px solid #33445F;
    border-radius: 6px;
    padding: 6px 8px;
    min-height: 22px;
}
QTabWidget::pane {
    border: 1px solid #263550;
    background: #0B1220;
}
QTabBar::tab {
    background: #111B2E;
    color: #9DAAC0;
    padding: 9px 20px;
    border: 1px solid #263550;
}
QTabBar::tab:selected {
    color: #E6C56E;
    background: #16233A;
}
QTableWidget {
    background: #0D1728;
    alternate-background-color: #101D31;
    border: 1px solid #263550;
    gridline-color: #263550;
}
QHeaderView::section {
    background: #16233A;
    color: #D9E1EE;
    border: none;
    padding: 6px;
    font-weight: 600;
}
"""
