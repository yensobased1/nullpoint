"""Our own crosshair share-code format (XH4, reads XH1-XH3 too). Not compatible with VALORANT codes, on purpose.

XH2;m:l;c:00FFFF;o:1,1,0.5;d:1,2,1;i:1,6,2,3,0.8,0,6;e:0,2,2,10,0.35,0,2;p:100,1,0;s:c;r:0;
    g:0,10,1,1,0,20,0;k:1,00FFFF,00FFFF,00FFFF,000000;w:0,5,1
See README.md for the field list.
"""
import copy
import re
from urllib.parse import quote, unquote

from config import DEFAULT_CROSSHAIR

VERSION = "XH4"
# XH1: no shapes/ring/colors; XH2: no shadow/gradient/style/text; XH3: no arms/dot shape/glow/expand
READABLE = ("XH1", "XH2", "XH3", "XH4")
MAX_CODE = 2048  # anything longer is not a crosshair code

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
    "h": ("shadow", [("on", bool, 0, 1), ("size", int, 0, 8), ("alpha", float, 0, 1)]),
    "a": ("arms", [("link", bool, 0, 1), ("t", int, 0, 30), ("r", int, 0, 30), ("b", int, 0, 30), ("l", int, 0, 30)]),
    "f": ("expand", [("on", bool, 0, 1), ("px", int, 0, 20), ("ms", int, 0, 500)]),
}
ARM_COLORS = ("ct", "cr", "cb", "cl")
DOT_SHAPES = {"s": "square", "c": "circle", "d": "diamond"}
DOT_KEYS = {v: k for k, v in DOT_SHAPES.items()}
HALO = {"s": "shadow", "g": "glow"}
HALO_KEYS = {v: k for k, v in HALO.items()}
MODES = {"l": "lines", "p": "png", "t": "text"}
MODE_KEYS = {v: k for k, v in MODES.items()}
SHAPES = {"c": "cross", "t": "t", "d": "dot", "o": "circle", "q": "square", "v": "chevron", "x": "x",
          "6": "hexagon", "3": "triangle", "4": "diamond", "p": "plus"}
STYLES = {"s": "solid", "d": "dashed", "o": "dotted"}
STYLE_KEYS = {v: k for k, v in STYLES.items()}
SHAPE_KEYS = {v: k for k, v in SHAPES.items()}
COLOR_PARTS = ("lines", "dot", "ring", "outline")
HEX = re.compile(r"[0-9A-Fa-f]{6}")


class ShareCodeError(ValueError):
    pass


def _float(raw, key):
    try:
        return float(raw)
    except ValueError:
        raise ShareCodeError(f"Bad number '{raw}' in '{key}'.") from None


def _clamp_int(raw, lo, hi, key):
    return min(max(round(_float(raw, key)), lo), hi)


def _num(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return f"{round(v, 2):g}"
    return str(v)


def export_code(cross):
    parts = [VERSION, "m:" + MODE_KEYS.get(cross["mode"], "l"), "c:" + cross["color"].upper()]
    for key, (sec, fields) in FIELDS.items():
        parts.append(key + ":" + ",".join(_num(cross[sec][f]) for f, *_ in fields))
    parts += ["s:" + SHAPE_KEYS.get(cross["shape"], "c"), "r:" + str(cross["rot"]),
              "k:" + ",".join([_num(cross["colors"]["same"])] + [cross["colors"][k].upper() for k in COLOR_PARTS]),
              "y:" + _num(cross["gradient"]["on"]) + "," + cross["gradient"]["c2"].upper(),
              "l:" + ",".join([STYLE_KEYS.get(cross["style"]["kind"], "s"), str(cross["style"]["dash"]),
                               str(cross["style"]["gap"])])]
    hexes = lambda v: v.upper() if isinstance(v, str) and HEX.fullmatch(v) else ""  # bad config value -> default
    parts += ["z:" + DOT_KEYS.get(cross["dot"]["shape"], "s"),
              "q:" + HALO_KEYS.get(cross["shadow"]["mode"], "s") + "," + (hexes(cross["shadow"]["color"]) or "FFFFFF"),
              "u:" + ",".join(hexes(cross["arms"][k]) for k in ARM_COLORS)]
    tx = cross["text"]
    # Text and font are percent-encoded so ; , : can never break the code.
    parts.append("x:" + ",".join([quote(tx["chars"], safe=""), str(tx["size"]), _num(tx["bold"]),
                                  _num(tx["alpha"]), quote(tx["font"], safe="")]))
    return ";".join(parts)


def import_code(text):
    """Code -> full crosshair dict. Missing keys/fields = defaults, unknown keys ignored."""
    text = (text or "").strip()
    if len(text) > MAX_CODE:
        raise ShareCodeError("That code is too long to be a crosshair code.")
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
        elif key == "y":
            vals = val.split(",")
            cross["gradient"]["on"] = vals[0] not in ("", "0")
            if len(vals) > 1 and vals[1]:
                if not HEX.fullmatch(vals[1]):
                    raise ShareCodeError(f"Bad color '{vals[1]}' (expected RRGGBB hex).")
                cross["gradient"]["c2"] = vals[1].upper()
        elif key == "l":
            vals = val.split(",")
            cross["style"]["kind"] = STYLES.get(vals[0].lower(), "solid")
            for name, raw in zip(("dash", "gap"), vals[1:]):
                cross["style"][name] = _clamp_int(raw, 1, 10, key)
        elif key == "x":
            vals = val.split(",")
            tx = cross["text"]
            tx["chars"] = unquote(vals[0])[:3]
            if len(vals) > 1 and vals[1]:
                tx["size"] = _clamp_int(vals[1], 8, 96, key)
            if len(vals) > 2 and vals[2]:
                tx["bold"] = vals[2] != "0"
            if len(vals) > 3 and vals[3]:
                tx["alpha"] = min(max(round(_float(vals[3], key), 2), 0.0), 1.0)
            if len(vals) > 4:
                tx["font"] = unquote(vals[4])[:64]
        elif key == "z":
            cross["dot"]["shape"] = DOT_SHAPES.get(val.lower(), "square")
        elif key == "q":
            vals = val.split(",")
            cross["shadow"]["mode"] = HALO.get(vals[0].lower(), "shadow")
            if len(vals) > 1 and vals[1]:
                if not HEX.fullmatch(vals[1]):
                    raise ShareCodeError(f"Bad color '{vals[1]}' (expected RRGGBB hex).")
                cross["shadow"]["color"] = vals[1].upper()
        elif key == "u":
            for name, v in zip(ARM_COLORS, val.split(",")):
                if v and not HEX.fullmatch(v):
                    raise ShareCodeError(f"Bad color '{v}' (expected RRGGBB hex).")
                cross["arms"][name] = v.upper()
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
