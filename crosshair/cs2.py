"""Convert pasted Counter-Strike 2 / CS:GO crosshair share codes (CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx).
Text parsing only: nothing is fetched from anywhere.

A code is a base-57 number holding 18 bytes (byte 0 = checksum of the rest). Byte layout follows the
open-source decoder used by the CS community (akiver/csgo-sharecode). Sizes follow the Source engine's crosshair
drawing: values are in 640x480 units, scaled by screen height / 480 (YRES), so CS crosshairs DO grow with resolution.
"""
import copy
import re

from config import DEFAULT_CROSSHAIR
from share_code import ShareCodeError

ALPHABET = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"
CODE_RE = re.compile(r"CSGO(-[A-Za-z0-9]{5}){5}")
# cl_crosshaircolor 0-4 presets (CS:GO / CS2 values); 5 = custom r/g/b.
PRESETS = {0: (250, 50, 50), 1: (50, 250, 50), 2: (250, 250, 50), 3: (50, 50, 250), 4: (50, 250, 250)}


def is_cs2(text):
    return (text or "").strip().upper().startswith("CSGO-")


def code_bytes(text):
    if len(text or "") > 200:
        raise ShareCodeError("That code is too long to be a CS2 crosshair code.")
    code = re.sub(r"\s+", "", text or "")
    if not CODE_RE.fullmatch(code):
        raise ShareCodeError("Not a CS2 crosshair code (expected CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx).")
    num = 0
    for ch in reversed(code[5:].replace("-", "")):
        i = ALPHABET.find(ch)
        if i < 0:
            raise ShareCodeError(f"'{ch}' can't appear in a CS2 crosshair code.")
        num = num * 57 + i
    if num >= 1 << 144:
        raise ShareCodeError("That CS2 crosshair code is damaged.")
    b = num.to_bytes(18, "big")
    if b[0] != sum(b[1:]) % 256:
        raise ShareCodeError("That CS2 crosshair code is damaged (checksum mismatch).")
    return b


def int8(v):
    return v - 256 if v > 127 else v


def decode(text):
    """-> dict of CS2 crosshair settings (cl_crosshair* values)."""
    b = code_bytes(text)
    return {
        "gap": int8(b[2]) / 10, "outline": b[3] / 2, "red": b[4], "green": b[5], "blue": b[6], "alpha": b[7],
        "color": b[10] & 7, "outline_on": bool(b[10] & 8), "thickness": b[12] / 10,
        "dot": bool((b[13] >> 4) & 1), "use_alpha": bool((b[13] >> 4) & 4), "t_style": bool((b[13] >> 4) & 8),
        "style": (b[13] & 0xF) >> 1, "size": (((b[15] & 0x1F) << 8) + b[14]) / 10,
    }


def convert(text, screen_height=1080):
    """CS2 code -> Nullpoint crosshair dict, drawn like the game's static crosshair at this screen height."""
    s = decode(text)
    yres = lambda v: v * screen_height / 480  # Source engine YRES()
    thick = max(1, round(yres(s["thickness"])))
    size = round(yres(s["size"]))
    # Source draws each bar starting (distance + thickness/2) px from the center; distance = YRES(4 + gap).
    distance = round(yres(4 + s["gap"]))
    gap = max(0, distance + thick // 2)
    cross = copy.deepcopy(DEFAULT_CROSSHAIR)
    r, g, bl = (s["red"], s["green"], s["blue"]) if s["color"] == 5 or s["color"] not in PRESETS else PRESETS[s["color"]]
    cross["color"] = f"{r:02X}{g:02X}{bl:02X}"
    cross["colors"]["same"] = True
    alpha = round((s["alpha"] if s["use_alpha"] else 200) / 255, 2)  # cl_crosshairusealpha 0 = fixed 200
    cross["outline"].update(on=s["outline_on"], thick=min(max(round(s["outline"]), 1), 6), alpha=1.0)
    cross["dot"].update(on=s["dot"], size=min(thick, 10), alpha=alpha)
    cross["inner"].update(on=size > 0, len=min(size, 30), thick=min(thick, 10), gap=min(gap, 40), alpha=alpha,
                          vsep=False, vlen=min(size, 30))
    cross["outer"]["on"] = False
    cross.update(mode="lines", shape="t" if s["t_style"] else "cross", rot=0)
    return cross
