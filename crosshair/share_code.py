"""Our own crosshair share-code format (XH2, reads XH1 too). Not compatible with VALORANT codes, on purpose.

XH2;m:l;c:00FFFF;o:1,1,0.5;d:1,2,1;i:1,6,2,3,0.8,0,6;e:0,2,2,10,0.35,0,2;p:100,1,0;s:c;r:0;
    g:0,10,1,1,0,20,0;k:1,00FFFF,00FFFF,00FFFF,000000;w:0,5,1
See README.md for the field list.
"""
import copy
import re

from config import DEFAULT_CROSSHAIR

VERSION = "XH2"
READABLE = ("XH1", "XH2")  # XH1 = before shapes/ring/colors/rainbow

LINE = [("on", bool, 0, 1), ("len", int, 0, 30), ("thick", int, 1, 10), ("gap", int, 0, 40),
        ("alpha", float, 0, 1), ("vsep", bool, 0, 1), ("vlen", int, 0, 30)]
# code key -> (settings section, [(field, type, min, max)]). Also the UI's slider ranges.
FIELDS = {
    "o": ("outline", [("on", bool, 0, 1), ("thick", int, 1, 6), ("alpha", float, 0, 1)]),
    "d": ("dot", [("on", bool, 0, 1), ("size", int, 1, 10), ("alpha", float, 0, 1)]),
    "i": ("inner", LINE),
    "e": ("outer", LINE),
    "p": ("png", [("scale", int, 10, 400), ("alpha", float, 0, 1), ("rot", int, 0, 270)]),
    "g": ("ring", [("on", bool, 0, 1), ("radius", int, 1, 50), ("thick", int, 1, 10), ("alpha", float, 0, 1),
                   ("gaps", int, 0, 8), ("gapsize", int, 0, 90), ("gaprot", int, 0, 359)]),
    "w": ("rainbow", [("on", bool, 0, 1), ("speed", int, 1, 10), ("sat", float, 0, 1)]),
}
MODES = {"l": "lines", "p": "png"}
SHAPES = {"c": "cross", "t": "t", "d": "dot", "o": "circle", "q": "square", "v": "chevron", "x": "x"}
SHAPE_KEYS = {v: k for k, v in SHAPES.items()}
COLOR_PARTS = ("lines", "dot", "ring", "outline")
HEX = re.compile(r"[0-9A-Fa-f]{6}")


class ShareCodeError(ValueError):
    pass


def _num(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return f"{round(v, 2):g}"
    return str(v)


def export_code(cross):
    parts = [VERSION, "m:" + ("p" if cross["mode"] == "png" else "l"), "c:" + cross["color"].upper()]
    for key, (sec, fields) in FIELDS.items():
        parts.append(key + ":" + ",".join(_num(cross[sec][f]) for f, *_ in fields))
    parts += ["s:" + SHAPE_KEYS.get(cross["shape"], "c"), "r:" + str(cross["rot"]),
              "k:" + ",".join([_num(cross["colors"]["same"])] + [cross["colors"][k].upper() for k in COLOR_PARTS])]
    return ";".join(parts)


def import_code(text):
    """Code -> full crosshair dict. Missing keys/fields = defaults, unknown keys ignored."""
    text = (text or "").strip()
    parts = [p for p in text.split(";") if p.strip()]
    if not parts or parts[0].strip().upper() not in READABLE:
        raise ShareCodeError(f"Not a crosshair code (must start with {VERSION} or XH1).")
    cross = copy.deepcopy(DEFAULT_CROSSHAIR)
    for part in parts[1:]:
        key, sep, val = part.strip().partition(":")
        if not sep:
            raise ShareCodeError(f"Bad part '{part}' (expected key:value).")
        key = key.lower()
        if key == "m":
            cross["mode"] = MODES.get(val.lower(), "lines")
        elif key == "c":
            if not HEX.fullmatch(val):
                raise ShareCodeError(f"Bad color '{val}' (expected RRGGBB hex).")
            cross["color"] = val.upper()
        elif key == "s":
            cross["shape"] = SHAPES.get(val.lower(), "cross")
        elif key == "r":
            try:
                cross["rot"] = min(max(round(float(val)), 0), 90)
            except ValueError:
                raise ShareCodeError(f"Bad rotation '{val}'.") from None
        elif key == "k":
            vals = val.split(",")
            if vals and vals[0] != "":
                cross["colors"]["same"] = vals[0] != "0"
            for part, v in zip(COLOR_PARTS, vals[1:]):
                if v and not HEX.fullmatch(v):
                    raise ShareCodeError(f"Bad color '{v}' (expected RRGGBB hex).")
                if v:
                    cross["colors"][part] = v.upper()
        elif key in FIELDS:
            sec, fields = FIELDS[key]
            for raw, (name, typ, lo, hi) in zip(val.split(","), fields):
                if raw == "":
                    continue
                try:
                    num = float(raw)
                except ValueError:
                    raise ShareCodeError(f"Bad number '{raw}' in '{key}'.") from None
                num = min(max(num, lo), hi)
                cross[sec][name] = bool(num) if typ is bool else round(num) if typ is int else round(num, 2)
        # unknown keys: ignored so newer codes still load
    if cross["png"]["rot"] not in (0, 90, 180, 270):
        cross["png"]["rot"] = 90 * round(cross["png"]["rot"] / 90) % 360
    return cross
