"""Color/spacing tokens + one QSS stylesheet built from them. Theme switch = swap tokens."""
import winreg

DARK = {
    "bg": "#1d2025", "panel": "#252930", "input": "#16181c", "border": "#3a3f48", "text": "#e6e8eb",
    "muted": "#9aa1ab", "accent": "#36b3c4", "accent_text": "#0b1a1d", "danger": "#ef6b6b",
    "ok": "#52c98e", "preview_top": "#3a4048", "preview_bottom": "#8a9099",
    "pad": "6px", "radius": "4px", "font": "10pt",
}
LIGHT = {
    "bg": "#f3f4f6", "panel": "#ffffff", "input": "#ffffff", "border": "#c9ced6", "text": "#1d2025",
    "muted": "#5d6470", "accent": "#0f8a9c", "accent_text": "#ffffff", "danger": "#c62828",
    "ok": "#1b8a4c", "preview_top": "#5a6370", "preview_bottom": "#c3c8cf",
    "pad": "6px", "radius": "4px", "font": "10pt",
}
tokens = dict(DARK)


def system_is_light():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 1
    except OSError:
        return False


def use(name):
    """name: System / Dark / Light. Returns the stylesheet for QApplication.setStyleSheet."""
    light = name == "Light" or (name == "System" and system_is_light())
    tokens.clear()
    tokens.update(LIGHT if light else DARK)
    return QSS.format(**tokens)


QSS = """
QWidget {{ background: {bg}; color: {text}; font-size: {font}; }}
QGroupBox {{ background: {panel}; border: 1px solid {border}; border-radius: {radius};
             margin-top: 14px; padding: {pad}; padding-top: 10px; font-weight: bold; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {accent}; }}
QGroupBox QWidget {{ background: {panel}; font-weight: normal; }}
QTabWidget::pane {{ border: 1px solid {border}; border-radius: {radius}; }}
QTabBar::tab {{ background: {panel}; border: 1px solid {border}; padding: 6px 12px; margin-right: 2px;
               border-top-left-radius: {radius}; border-top-right-radius: {radius}; }}
QTabBar::tab:selected {{ background: {accent}; color: {accent_text}; }}
QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: {radius}; padding: 5px 10px; }}
QPushButton:hover {{ border-color: {accent}; }}
QPushButton:pressed {{ background: {accent}; color: {accent_text}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QKeySequenceEdit, QListWidget, QTableWidget {{
    background: {input}; border: 1px solid {border}; border-radius: {radius}; padding: 3px; }}
QComboBox QAbstractItemView {{ background: {input}; selection-background-color: {accent}; }}
QHeaderView::section {{ background: {panel}; border: 0; border-bottom: 1px solid {border}; padding: 4px; }}
QListWidget::item:selected, QTableWidget::item:selected {{ background: {accent}; color: {accent_text}; }}
QSlider::groove:horizontal {{ height: 4px; background: {border}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; margin: -6px 0; border-radius: 7px; background: {accent}; }}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
QPushButton:checked {{ background: {accent}; color: {accent_text}; border-color: {accent}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {muted}; border-radius: 3px;
                        background: {input}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
QScrollBar:vertical {{ background: {bg}; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QScrollArea {{ border: 0; }}
QLabel#muted {{ color: {muted}; }}
"""
