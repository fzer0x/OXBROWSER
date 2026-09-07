# Professional Flat Dark Theme for OXBROWSER
# Designed for maximum clarity, serious tone, and high performance.

DARK_STYLESHEET = """
/* ==========================================================================
   GLOBAL CANVAS & TYPOGRAPHY
   ========================================================================== */
QMainWindow, QDialog {
    background-color: #121212;
    color: #f0f0f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", "Ubuntu", sans-serif;
    font-size: 13px;
    selection-background-color: rgba(37, 99, 235, 0.4);
    selection-color: #ffffff;
}

QWidget {
    background-color: transparent;
    color: #e5e5e5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", "Ubuntu", sans-serif;
    font-size: 13px;
}

QWidget:disabled {
    color: #666666;
}

/* ==========================================================================
   SIDEBAR & BRANDING
   ========================================================================== */
#SidebarWidget {
    background-color: #18181a;
    border-right: 1px solid #2d2d2f;
}

#SidebarHeader {
    padding: 14px 14px 12px 14px;
    border-bottom: 1px solid #2d2d2f;
    margin-bottom: 8px;
}

#SidebarLogo {
    background-color: transparent;
    padding: 0px;
}

#SidebarTitle {
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.3px;
}

#SidebarBadge {
    background-color: rgba(37, 99, 235, 0.18);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.35);
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.3px;
}

#SidebarSubtitle {
    font-size: 11px;
    color: #888888;
    font-weight: 500;
    margin-top: 2px;
}

QPushButton.NavButton {
    background-color: transparent;
    color: #999999;
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 500;
    border: 1px solid transparent;
    border-radius: 6px;
    margin: 2px 8px;
}

QPushButton.NavButton:hover {
    background-color: #232325;
    color: #e5e5e5;
}

QPushButton.NavButton:checked {
    background-color: #2a2a2d;
    color: #ffffff;
    font-weight: 600;
    border-left: 3px solid #2563eb;
    border-radius: 6px;
}

/* ==========================================================================
   CARDS & METRICS
   ========================================================================== */
#HeaderWidget {
    background-color: #121212;
    border-bottom: 1px solid #2d2d2f;
    padding: 10px 16px;
}

QFrame.MetricCard, #SystemResourceCard {
    background-color: #1a1a1c;
    border: 1px solid #2d2d2f;
    border-radius: 8px;
}

QFrame.MetricCard:hover, #SystemResourceCard:hover {
    border: 1px solid #3d3d40;
}

QLabel.MetricValue {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.2px;
}

QLabel.MetricTitle {
    font-size: 11px;
    font-weight: 600;
    color: #888888;
    letter-spacing: 0.4px;
}

/* ==========================================================================
   TABLES & DATA GRIDS
   ========================================================================== */
QTableWidget {
    background-color: #161618;
    gridline-color: #2a2a2c;
    border: 1px solid #2d2d2f;
    border-radius: 8px;
    selection-background-color: rgba(37, 99, 235, 0.25);
    selection-color: #ffffff;
    alternate-background-color: #1a1a1c;
    outline: none;
}

QTableWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #2a2a2c;
    color: #d1d5db;
}

QTableWidget::item:selected {
    background-color: rgba(37, 99, 235, 0.25);
    color: #ffffff;
}

QTableWidget::item:hover {
    background-color: #1e1e20;
}

QHeaderView::section {
    background-color: #18181a;
    color: #888888;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.3px;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #2d2d2f;
    text-transform: uppercase;
}

/* ==========================================================================
   BUTTONS & ACTIONS
   ========================================================================== */
QPushButton {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", "Ubuntu", sans-serif;
    font-size: 12px;
    font-weight: 500;
    padding: 7px 14px;
    border-radius: 6px;
    outline: none;
}

/* Unified Professional Blue Buttons */
QPushButton.PrimaryButton, QPushButton.SuccessButton, QPushButton.DangerButton {
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 600;
    border: 1px solid #1d4ed8;
}

QPushButton.PrimaryButton:hover, QPushButton.SuccessButton:hover, QPushButton.DangerButton:hover {
    background-color: #3b82f6;
    border: 1px solid #2563eb;
}

QPushButton.PrimaryButton:pressed, QPushButton.SuccessButton:pressed, QPushButton.DangerButton:pressed {
    background-color: #1d4ed8;
}

/* Secondary Button (Subtle styling) */
QPushButton.SecondaryButton {
    background-color: #232325;
    color: #e5e5e5;
    font-weight: 500;
    border: 1px solid #333333;
}

QPushButton.SecondaryButton:hover {
    background-color: #2a2a2d;
    color: #ffffff;
    border-color: #404040;
}

QPushButton.SecondaryButton:pressed {
    background-color: #1a1a1c;
}

/* ==========================================================================
   INPUTS & FORM CONTROLS
   ========================================================================== */
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #161618;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 7px 10px;
    color: #f0f0f0;
    font-size: 13px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QLineEdit:hover, QComboBox:hover, QTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #404040;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #2563eb;
    background-color: #18181a;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
    margin-right: 4px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888888;
    width: 0;
    height: 0;
    margin-top: 2px;
}

QComboBox QAbstractItemView {
    background-color: #18181a;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 4px;
    color: #f0f0f0;
    selection-background-color: rgba(37, 99, 235, 0.3);
    selection-color: #ffffff;
    outline: none;
}

/* ==========================================================================
   TABS & GROUP BOXES
   ========================================================================== */
QTabWidget::pane {
    border: 1px solid #2d2d2f;
    background-color: #161618;
    border-radius: 8px;
    top: -1px;
    padding: 10px;
}

QTabBar::tab {
    background-color: transparent;
    color: #888888;
    padding: 9px 18px;
    border: 1px solid transparent;
    border-bottom: none;
    margin-right: 4px;
    font-weight: 500;
    font-size: 12px;
}

QTabBar::tab:hover {
    color: #e5e5e5;
    background-color: #1a1a1c;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #161618;
    color: #2563eb;
    font-weight: 600;
    border: 1px solid #2d2d2f;
    border-bottom: 1px solid #161618;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QGroupBox {
    background-color: #161618;
    border: 1px solid #2d2d2f;
    border-radius: 8px;
    margin-top: 18px;
    padding-top: 18px;
    padding-left: 12px;
    padding-right: 12px;
    padding-bottom: 12px;
    font-weight: 600;
    font-size: 12px;
    color: #e5e5e5;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    background-color: #121212;
    border-radius: 4px;
    color: #888888;
}

/* ==========================================================================
   PROGRESS BARS
   ========================================================================== */
QProgressBar {
    background-color: #232325;
    border: 1px solid #2d2d2f;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
    min-height: 14px;
}

QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 3px;
}

/* ==========================================================================
   CHECKBOXES & RADIOS
   ========================================================================== */
QCheckBox, QRadioButton {
    color: #d1d5db;
    font-size: 12px;
    spacing: 7px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    background-color: #161618;
    border: 1px solid #404040;
    border-radius: 4px;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #2563eb;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

/* ==========================================================================
   MINIMALIST SLIM SCROLLBARS
   ========================================================================== */
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 2px 0 2px 0;
}

QScrollBar::handle:vertical {
    background-color: #333333;
    border-radius: 4px;
    min-height: 25px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4d4d4d;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    height: 0px;
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 0 2px 0 2px;
}

QScrollBar::handle:horizontal {
    background-color: #333333;
    border-radius: 4px;
    min-width: 25px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #4d4d4d;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    width: 0px;
    background: none;
}

/* ==========================================================================
   MENUS & TOOLTIPS
   ========================================================================== */
QMenu {
    background-color: #18181a;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
    color: #d1d5db;
}

QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QToolTip {
    background-color: #1a1a1c;
    color: #f0f0f0;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 11px;
}

QSplitter::handle {
    background-color: #2d2d2f;
}

QSplitter::handle:hover {
    background-color: #404040;
}
"""
