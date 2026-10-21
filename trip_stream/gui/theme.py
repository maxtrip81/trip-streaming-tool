"""Dark stylesheet shared by all windows."""

STYLE = """
QWidget { background: #141a1d; color: #dfe7e5; font-size: 13px; }
QToolTip { background: #20292d; color: #dfe7e5; border: 1px solid #33413f; }
QGroupBox { border: 1px solid #2a3538; border-radius: 6px; margin-top: 14px; padding: 8px 6px 6px 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #8fb3aa; font-weight: 600; }
QPushButton, QToolButton { background: #222c30; border: 1px solid #33413f; border-radius: 5px; padding: 5px 10px; }
QPushButton:hover, QToolButton:hover { background: #2b383d; border-color: #4a5d5a; }
QPushButton:pressed, QToolButton:pressed { background: #1a2225; }
QPushButton:disabled, QToolButton:disabled { color: #5d6866; }
QToolButton#transport { font-size: 18px; min-width: 44px; min-height: 34px; padding: 2px 6px; }
QToolButton#transport:checked { background: #173a30; border-color: #38f2b0; }
QToolButton#record:checked { background: #44171c; border-color: #ff4d5a; color: #ff4d5a; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QListWidget {
    background: #0e1315; border: 1px solid #2f3b3e; border-radius: 4px; padding: 3px 5px;
    selection-background-color: #1f6b56; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { color: #5d6866; background: #12181a; }
QScrollArea { border: none; }
QComboBox QAbstractItemView { background: #0e1315; selection-background-color: #1f6b56; }
QTabWidget::pane { border: 1px solid #2a3538; border-radius: 6px; top: -1px; }
QTabBar::tab { background: #1a2225; border: 1px solid #2a3538; padding: 6px 12px; border-top-left-radius: 5px;
    border-top-right-radius: 5px; margin-right: 2px; }
QTabBar::tab:selected { background: #222c30; color: #38f2b0; }
QSlider::groove:horizontal { height: 4px; background: #2a3538; border-radius: 2px; }
QSlider::groove:vertical { width: 4px; background: #2a3538; border-radius: 2px; }
QSlider::handle:horizontal, QSlider::handle:vertical { background: #38f2b0; border-radius: 6px; width: 12px;
    height: 12px; margin: -5px; }
QCheckBox::indicator, QListWidget::indicator { width: 13px; height: 13px; border: 1px solid #4a5d5a;
    border-radius: 3px; background: #0e1315; }
QCheckBox::indicator:checked, QListWidget::indicator:checked { background: #38f2b0; border-color: #38f2b0; }
QCheckBox::indicator:disabled { background: #1a2225; }
QLabel#hint { color: #8a9a96; font-size: 12px; }
QLabel#brand { color: #38f2b0; font-weight: 700; letter-spacing: 2px; }
QStatusBar { color: #8a9a96; }
"""
