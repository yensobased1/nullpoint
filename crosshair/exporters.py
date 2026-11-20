"""Nullpoint crosshair -> other games: a VALORANT code and CS2 console commands.

Both games draw fewer things than Nullpoint, so export returns the closest match plus a list of what was lost.
CS2 share codes (CSGO-...) are NOT generated: the encoder couldn't be checked against real codes made by the game.
"""
from valorant import COLORS


def _f(v):
    return f"{round(v, 3):g}"


def to_valorant(cross):
    """-> (code, warnings). Raises ValueError for image / text crosshairs (VALORANT has no equivalent)."""
    if cross["mode"] != "lines":
        raise ValueError("Image and text crosshairs can't be turned into a VALORANT code.")
    warn = []
    shape = cross["shape"]
    if shape not in ("cross", "dot"):
        warn.append(f"Shape '{shape}' isn't in VALORANT: exported as a plain cross.")
    for cond, text in ((cross["rot"], "Line rotation"), (cross["ring"]["on"], "Ring"),
                       (not cross["arms"]["link"], "Per-arm lengths and colors"),
                       (cross["dot"]["shape"] != "square" and cross["dot"]["on"], "Round / diamond dot"),
                       (cross["shadow"]["on"], "Shadow / glow"), (cross["gradient"]["on"], "Gradient"),
                       (cross["rainbow"]["on"], "Rainbow"), (cross["style"]["kind"] != "solid", "Dashed / dotted lines"),
                       (not cross["colors"]["same"], "Separate part colors"), (cross["expand"]["on"], "Fire expand")):
        if cond:
            warn.append(f"{text}: not available in VALORANT, left out.")
    col = (cross["color"] if cross["colors"]["same"] else cross["colors"]["lines"]).upper()
    parts = ["0", "P"]
    parts += ["c", str(COLORS.index(col))] if col in COLORS else ["c", "8", "u", col + "FF"]
    ol = cross["outline"]
    parts += ["h", "1" if ol["on"] else "0", "t", str(min(ol["thick"], 6)), "o", _f(ol["alpha"])]
    d = cross["dot"]
    parts += ["d", "1" if d["on"] else "0", "z", str(min(d["size"], 6)), "a", _f(d["alpha"])]
    if d["size"] > 6 and d["on"]:
        warn.append("Center dot bigger than 6 px: VALORANT's maximum is 6.")
    for n, sec in (("0", "inner"), ("1", "outer")):
        s = cross[sec]
        on = s["on"] and shape != "dot"
        clamp = lambda v, hi: min(v, hi)
        if on and (s["len"] > 20 or s["gap"] > 20 or (s["vsep"] and s["vlen"] > 20)):
            warn.append(f"{sec.capitalize()} lines: length / gap above 20 px were cut to 20 (VALORANT's maximum).")
        parts += [n + "b", "1" if on else "0", n + "t", str(s["thick"]), n + "l", str(clamp(s["len"], 20)),
                  n + "o", str(clamp(s["gap"], 20)), n + "a", _f(s["alpha"]), n + "m", "0", n + "f", "0"]
        if s["vsep"]:
            parts += [n + "g", "1", n + "v", str(clamp(s["vlen"], 20))]
    return ";".join(parts), warn


def to_cs2_commands(cross, screen_height=1080):
    """-> (console commands text, warnings). Sizes undo CS2's height / 480 scaling (see cs2.convert)."""
    if cross["mode"] != "lines":
        raise ValueError("Image and text crosshairs can't be turned into CS2 commands.")
    warn = []
    yres = screen_height / 480
    s = cross["inner"]
    thick = s["thick"]
    col = cross["color"] if cross["colors"]["same"] else cross["colors"]["lines"]
    r, g, b = (int(col[i:i + 2], 16) for i in (0, 2, 4))
    # Nullpoint gap px = round(yres * (4 + cs_gap)) + thick // 2  ->  cs_gap = (gap - thick // 2) / yres - 4
    gap = (s["gap"] - thick // 2) / yres - 4
    alpha = round(255 * s["alpha"])
    lines = [("cl_crosshairstyle", "4"), ("cl_crosshairsize", _f(s["len"] / yres if s["on"] else 0)),
             ("cl_crosshairthickness", _f(thick / yres)), ("cl_crosshairgap", _f(gap)),
             ("cl_crosshaircolor", "5"), ("cl_crosshaircolor_r", str(r)), ("cl_crosshaircolor_g", str(g)),
             ("cl_crosshaircolor_b", str(b)), ("cl_crosshairusealpha", "1"), ("cl_crosshairalpha", str(alpha)),
             ("cl_crosshair_drawoutline", "1" if cross["outline"]["on"] else "0"),
             ("cl_crosshair_outlinethickness", _f(min(cross["outline"]["thick"], 3))),
             ("cl_crosshairdot", "1" if cross["dot"]["on"] else "0"),
             ("cl_crosshair_t", "1" if cross["shape"] == "t" else "0")]
    if cross["shape"] not in ("cross", "t"):
        warn.append(f"Shape '{cross['shape']}' isn't in CS2: exported as a plain cross.")
    if cross["outer"]["on"]:
        warn.append("Outer lines: not available in CS2, left out.")
    if s["vsep"]:
        warn.append("Separate vertical length: not available in CS2.")
    for cond, text in ((cross["ring"]["on"], "Ring"), (cross["shadow"]["on"], "Shadow / glow"),
                       (cross["rot"], "Line rotation"), (not cross["arms"]["link"], "Per-arm settings")):
        if cond:
            warn.append(f"{text}: not available in CS2, left out.")
    return "; ".join(f"{k} {v}" for k, v in lines), warn
