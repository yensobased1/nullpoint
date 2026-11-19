"""Color/spacing tokens + one QSS stylesheet built from them. Theme switch = swap tokens."""
import winreg

# Monochrome (black & white) to match the Nullpoint brand. Only error text keeps a color.
DARK = {
    "bg": "#000000", "panel": "#0f0f0f", "input": "#000000", "border": "#2e2e2e", "text": "#f2f2f2",
    "muted": "#8c8c8c", "accent": "#ffffff", "accent_text": "#000000", "danger": "#ef6b6b",
    "ok": "#f2f2f2", "pad": "6px", "radius": "4px", "font": "10pt",
}
LIGHT = {
    "bg": "#ffffff", "panel": "#f4f4f4", "input": "#ffffff", "border": "#cccccc", "text": "#0a0a0a",
    "muted": "#5c5c5c", "accent": "#000000", "accent_text": "#ffffff", "danger": "#c62828",
    "ok": "#0a0a0a", "pad": "6px", "radius": "4px", "font": "10pt",
}
tokens = dict(DARK)


def system_is_light():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 1
    except OSError:
        return False


def use(name, scale=100, large=False):
    """name: System / Dark / Light; scale: text size %; large: +2 pt. Returns the settings stylesheet."""
    light = name == "Light" or (name == "System" and system_is_light())
    tokens.clear()
    tokens.update(LIGHT if light else DARK)
    tokens["font"] = f"{round(10 * scale / 100 + (2 if large else 0))}pt"
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
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QKeySequenceEdit, QListWidget, QTableWidget,
QTextBrowser, QTextEdit, QPlainTextEdit {{
    background: {input}; border: 1px solid {border}; border-radius: {radius}; padding: 3px;
    selection-background-color: {accent}; selection-color: {accent_text}; }}
/* themed everywhere, so the Windows accent color (e.g. purple) never shows */
QToolButton {{ background: {panel}; border: 1px solid {border}; border-radius: {radius}; padding: 4px; }}
QToolButton:hover {{ border-color: {accent}; }}
QToolButton:checked, QToolButton:pressed {{ background: {accent}; color: {accent_text}; }}
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
/* Slider number boxes: zero-width buttons (Qt squeezes the text to 1px if NoButtons is combined with QSS) */
QAbstractSpinBox#num::up-button, QAbstractSpinBox#num::down-button {{ width: 0px; border: 0px; }}
/* keyboard focus rings */
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus, QKeySequenceEdit:focus,
QListWidget:focus, QTableWidget:focus, QTabBar::tab:focus, QTextBrowser:focus, QTextEdit:focus,
QPlainTextEdit:focus, QToolButton:focus {{ border: 2px solid {accent}; }}
QCheckBox:focus {{ text-decoration: underline; }}
QSlider:focus QSlider::handle:horizontal, QSlider::handle:horizontal:focus {{ border: 2px solid {muted}; }}
QScrollArea {{ border: 0; }}
QLabel#muted {{ color: {muted}; }}
"""
