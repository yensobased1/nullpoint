"""Translation report: for every lang/<code>.json, the keys missing or extra compared with en.json, and the
tr("...") texts in the code that en.json doesn't list yet. Missing keys simply show in English in the app.

    python lang_report.py          report only
    python lang_report.py --strict exit code 1 if anything is missing (used by the tests)
"""
import ast
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LANG = os.path.join(HERE, "lang")


def load(code):
    with open(os.path.join(LANG, code + ".json"), encoding="utf-8") as f:
        return json.load(f)


def code_keys():
    """Every literal string passed straight to tr() anywhere in the app."""
    found = set()
    for path in glob.glob(os.path.join(HERE, "**", "*.py"), recursive=True):
        if os.path.basename(path).startswith("test_"):
            continue
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "tr"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.add(node.args[0].value)
    return found


def report():
    en = set(load("en"))
    out = {"code_not_in_en": sorted(code_keys() - en), "languages": {}}
    for path in sorted(glob.glob(os.path.join(LANG, "*.json"))):
        code = os.path.splitext(os.path.basename(path))[0]
        if code != "en":
            keys = set(load(code))
            out["languages"][code] = {"missing": sorted(en - keys), "extra": sorted(keys - en)}
    return out


def main():
    r = report()
    bad = bool(r["code_not_in_en"])
    print(f"tr() texts missing from en.json: {len(r['code_not_in_en'])}")
    for k in r["code_not_in_en"]:
        print("   ", k)
    for code, d in r["languages"].items():
        print(f"{code:6} missing {len(d['missing']):4}   extra {len(d['extra']):4}")
        bad = bad or bool(d["missing"])
        for k in d["missing"][:20]:
            print("    missing:", k)
    return 1 if bad and "--strict" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
