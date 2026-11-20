"""Built-in starter packs: original crosshairs grouped by style (no real player names)."""
import copy

from config import DEFAULT_CROSSHAIR


def make(**kw):
    c = copy.deepcopy(DEFAULT_CROSSHAIR)
    c["dot"]["on"] = False
    for k, v in kw.items():
        c[k].update(v) if isinstance(v, dict) else c.__setitem__(k, v)
    return c


OL = {"on": True, "thick": 1, "alpha": 1.0}
NO_OL = {"on": False}
PACKS = {
    "Minimal": [
        ("Pin", make(inner={"len": 3, "thick": 1, "gap": 2}, outline=NO_OL, color="FFFFFF")),
        ("Hairline", make(inner={"len": 5, "thick": 1, "gap": 3}, outline=OL, color="00FF00")),
        ("Small plus", make(inner={"len": 2, "thick": 2, "gap": 0}, outline=OL, color="00FFFF")),
        ("Tight T", make(shape="t", inner={"len": 4, "thick": 1, "gap": 2}, outline=OL, color="FFFF00")),
        ("Ghost", make(inner={"len": 4, "thick": 2, "gap": 3, "alpha": 0.5}, outline=NO_OL, color="FFFFFF")),
    ],
    "Classic cross": [
        ("Classic green", make(inner={"len": 6, "thick": 2, "gap": 3}, outline=OL, color="00FF00")),
        ("Classic cyan", make(inner={"len": 6, "thick": 2, "gap": 3}, outline=OL, color="00FFFF")),
        ("Long thin", make(inner={"len": 10, "thick": 1, "gap": 4}, outline=OL, color="FFFFFF")),
        ("Bold", make(inner={"len": 7, "thick": 3, "gap": 4}, outline={"on": True, "thick": 2, "alpha": 1.0},
                      color="FFFF00")),
        ("Two layer", make(inner={"len": 4, "thick": 2, "gap": 2}, outer={"on": True, "len": 3, "thick": 2, "gap": 10,
                                                                          "alpha": 0.6}, outline=OL, color="FF00FF")),
        ("Dotted", make(inner={"len": 9, "thick": 2, "gap": 3}, style={"kind": "dotted", "gap": 2}, outline=OL,
                        color="00FF00")),
    ],
    "Dot": [
        ("Dot 2", make(shape="dot", dot={"on": True, "size": 2}, outline=OL, color="FFFFFF")),
        ("Dot 4 round", make(shape="dot", dot={"on": True, "size": 4, "shape": "circle"}, outline=OL, color="00FF00")),
        ("Diamond dot", make(shape="dot", dot={"on": True, "size": 5, "shape": "diamond"}, outline=OL, color="FF4D8D")),
        ("Glow dot", make(shape="dot", dot={"on": True, "size": 3, "shape": "circle"}, outline=NO_OL, color="00FFFF",
                          shadow={"on": True, "mode": "glow", "color": "00FFFF", "size": 4, "alpha": 0.6})),
        ("Big dot", make(shape="dot", dot={"on": True, "size": 6, "shape": "circle"}, outline=OL, color="FFFF00")),
    ],
    "Circle": [
        ("Ring", make(shape="circle", ring={"on": True, "radius": 10, "thick": 1}, outline=OL, color="FFFFFF")),
        ("Ring + dot", make(shape="circle", ring={"on": True, "radius": 8, "thick": 1}, dot={"on": True, "size": 2},
                            outline=OL, color="00FF00")),
        ("Split ring", make(shape="circle", ring={"on": True, "radius": 12, "thick": 2, "gaps": 4, "gapsize": 30,
                                                  "gaprot": 45}, outline=OL, color="00FFFF")),
        ("Quarter ring", make(shape="circle", ring={"on": True, "radius": 14, "thick": 2, "gaps": 4, "gapsize": 50},
                              dot={"on": True, "size": 2}, outline=OL, color="FFFF00")),
        ("Ring cross", make(ring={"on": True, "radius": 12, "thick": 1, "alpha": 0.7},
                            inner={"len": 4, "thick": 1, "gap": 3}, outline=OL, color="FF00FF")),
    ],
    "Pro-inspired": [
        ("Tiny static", make(inner={"len": 2, "thick": 2, "gap": 1}, outline=NO_OL, color="00FFFF")),
        ("Compact", make(inner={"len": 3, "thick": 2, "gap": 2}, outline=OL, color="00FF00")),
        ("Wide gap", make(inner={"len": 4, "thick": 2, "gap": 5}, dot={"on": True, "size": 2}, outline=OL,
                          color="FFFF00")),
        ("Short T", make(shape="t", inner={"len": 3, "thick": 2, "gap": 2}, outline=OL, color="FFFFFF")),
        ("Expanding", make(inner={"len": 4, "thick": 2, "gap": 2}, outline=OL, color="00FFFF",
                           expand={"on": True, "px": 4, "ms": 120})),
    ],
    "Fun": [
        ("Chevron", make(shape="chevron", inner={"len": 7, "thick": 2, "gap": 1}, outline=OL, color="FF4D8D")),
        ("Hexagon", make(shape="hexagon", inner={"len": 6, "thick": 1, "gap": 2}, outline=OL, color="00FFFF")),
        ("Rainbow", make(inner={"len": 6, "thick": 2, "gap": 3}, outline=OL, rainbow={"on": True, "speed": 4})),
        ("Gradient X", make(shape="x", inner={"len": 7, "thick": 2, "gap": 2}, outline=OL, color="FFFF00",
                            gradient={"on": True, "c2": "FF0000"})),
        ("Triangle", make(shape="triangle", inner={"len": 8, "thick": 1, "gap": 0}, outline=OL, color="00FF00")),
        ("Neon glow", make(inner={"len": 6, "thick": 2, "gap": 3}, outline=NO_OL, color="FF00FF",
                           shadow={"on": True, "mode": "glow", "color": "FF00FF", "size": 5, "alpha": 0.5})),
    ],
}
