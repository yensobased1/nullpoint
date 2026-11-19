"""UI strings. Keys are the English text; lang/<code>.json maps them to the translation."""
import json
import os
import sys

LANG_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "lang")
LANGUAGES = {"en": "English", "ar": "العربية"}
RTL = {"ar"}
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
    return _table.get(text) or text


def is_rtl():
    return current in RTL
