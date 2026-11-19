"""Convert pasted VALORANT crosshair codes (e.g. copied from vcrdb.net) into Nullpoint crosshairs.
Text parsing only: nothing is fetched from anywhere.

Format: ';'-separated key;value pairs after section markers: 0 = general, P = primary, A = aim down sights,
S = sniper. Only P is imported. Defaults below are VALORANT's own (Settings > Crosshair > Primary).
"""
import copy
import re

from config import DEFAULT_CROSSHAIR
from share_code import ShareCodeError, import_code

# VALORANT's 8 preset colors (same hex values the game's color picker shows), index 8 = custom (key u).
COLORS = ["FFFFFF", "00FF00", "7FFF00", "DFFF00", "FFFF00", "00FFFF", "FF00FF", "FF0000"]
DEFAULTS = {
    "c": 0, "h": 1, "t": 1, "o": 0.5, "d": 0, "z": 2, "a": 1.0,
    "0b": 1, "0t": 2, "0l": 6, "0g": 0, "0o": 3, "0a": 0.8,
    "1b": 1, "1t": 2, "1l": 2, "1g": 0, "1o": 10, "1a": 0.35,
}
KEY_RE = re.compile(r"[0-9a-z]{1,3}", re.I)
NUM_RE = re.compile(r"-?\d+(\.\d+)?")
HEX8_RE = re.compile(r"[0-9a-fA-F]{6}([0-9a-fA-F]{2})?")


def is_valorant(text):
    return (text or "").strip().startswith("0;")


def parse(text):
    """Code -> {section: {key: raw value}}. Raises ShareCodeError with a clear message."""
    tokens = [t.strip() for t in re.sub(r"\s+", "", text or "").split(";")]
    tokens = [t for t in tokens if t != ""]
    if not tokens or tokens[0] != "0":
        raise ShareCodeError("Not a VALORANT crosshair code (it must start with 0;).")
    if len(text) > 2000:
        raise ShareCodeError("That code is too long to be a VALORANT crosshair code.")
    sections, cur, i = {}, "0", 1
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        # Markers are P / A / S. Lowercase p/a/s are accepted too, unless a value follows: '0;s;1;P' has the
        # general-section key 's' (value 1) before the P marker.
        marker = tok in ("P", "A", "S") or (tok in ("p", "a", "s") and not NUM_RE.fullmatch(nxt))
        if marker:
            cur = tok.upper()
            i += 1
            continue
        if not KEY_RE.fullmatch(tok):
            raise ShareCodeError(f"Bad key '{tok[:12]}' in the VALORANT code.")
        if i + 1 >= len(tokens):
            raise ShareCodeError(f"Key '{tok}' has no value in the VALORANT code.")
        sections.setdefault(cur, {})[tok.lower()] = tokens[i + 1]
        i += 2
    return sections


def _num(raw, key):
    if not NUM_RE.fullmatch(raw):
        raise ShareCodeError(f"Bad value '{raw[:12]}' for '{key}' in the VALORANT code.")
    return float(raw)


def convert(text, scale=1.0):
    """VALORANT code -> Nullpoint crosshair dict. scale = game height / 1080 for in-game-accurate size."""
    p = parse(text).get("P", {})
    v = {}
    for k, default in DEFAULTS.items():
        v[k] = _num(p[k], k) if k in p else default
    for k in ("0v", "1v"):
        if k in p:
            v[k] = _num(p[k], k)
    px = lambda x: max(0, round(x * scale))  # whole pixels
    cross = copy.deepcopy(DEFAULT_CROSSHAIR)
    # Custom color: 'u' (RRGGBBAA) counts when c is 8 or c is missing; a preset index wins otherwise.
    custom = p.get("u")
    if custom is not None and not HEX8_RE.fullmatch(custom):
        raise ShareCodeError(f"Bad custom color '{custom[:12]}' in the VALORANT code.")
    idx = int(v["c"])
    if custom and ("c" not in p or idx == 8):
        cross["color"] = custom[:6].upper()
    else:
        cross["color"] = COLORS[idx] if 0 <= idx < len(COLORS) else COLORS[0]
    cross["colors"]["same"] = True
    cross["outline"].update(on=bool(v["h"]), thick=min(max(px(v["t"]), 1), 6), alpha=round(min(max(v["o"], 0), 1), 2))
    cross["dot"].update(on=bool(v["d"]), size=min(max(px(v["z"]), 1), 10), alpha=round(min(max(v["a"], 0), 1), 2))
    for n, sec in (("0", "inner"), ("1", "outer")):
        thick, length = px(v[n + "t"]), px(v[n + "l"])
        vsep = bool(v[n + "g"])
        vlen = px(v.get(n + "v", v[n + "l"]))
        cross[sec].update(on=bool(v[n + "b"]) and thick > 0 and (length > 0 or (vsep and vlen > 0)),
                          thick=min(max(thick, 1), 10), len=min(length, 30), gap=min(px(v[n + "o"]), 40),
                          alpha=round(min(max(v[n + "a"], 0), 1), 2), vsep=vsep, vlen=min(vlen, 30))
    cross.update(mode="lines", shape="cross", rot=0)
    return cross


def import_any(text, scale=1.0):
    """Nullpoint (XH...) or VALORANT (0;...) code -> (crosshair, 'nullpoint' | 'valorant')."""
    text = (text or "").strip()
    if is_valorant(text):
        return convert(text, scale), "valorant"
    return import_code(text), "nullpoint"
