"""UI strings. Keys are the English text; lang/<code>.json maps them to the translation."""
import json
import os
import sys

LANG_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "lang")
# Everything except en / ar is machine-translated: fixes welcome (see docs/TRANSLATING.md).
LANGUAGES = {"en": "English", "ar": "العربية", "de": "Deutsch", "es": "Español", "fr": "Français",
             "it": "Italiano", "pl": "Polski", "pt_BR": "Português (Brasil)", "ru": "Русский", "tr": "Türkçe",
             "ja": "日本語", "ko": "한국어", "zh_CN": "简体中文"}
RTL = {"ar"}
# Windows' own CJK UI fonts, so Han characters get the right regional shapes (Japanese vs Chinese glyphs).
FONTS = {"ja": "Yu Gothic UI", "ko": "Malgun Gothic", "zh_CN": "Microsoft YaHei UI"}
_table = {}
current = "en"


def set_language(code):
    global _table, current
    current = code if code in LANGUAGES else "en"
    try:
        with open(os.path.join(LANG_DIR, current + ".json"), encoding="utf-8") as f:
            _table = json.load(f)
    except (OSError, ValueError):
        _table = {}  # missing/broken file: fall back to English keys


seen = set()  # every key asked for at runtime: used to (re)build lang/en.json and check ar.json


def tr(text):
    seen.add(text)
    return _table.get(text) or text  # missing key: English


def ui_font(base):
    """The app font for the current language: base family, or the CJK UI font first with base as fallback."""
    from PySide6.QtGui import QFont
    f = QFont(base)
    fam = FONTS.get(current)
    f.setFamilies([fam, base.family()] if fam else [base.family()])
    return f


def is_rtl():
    return current in RTL
