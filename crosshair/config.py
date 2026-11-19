"""Load/save config JSON in %APPDATA%\\Nullpoint\\config.json."""
import copy
import json
import os
import shutil
import time

import sys

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
EXE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None
# Portable mode: portable.txt next to Nullpoint.exe -> keep everything in a "data" folder beside it.
PORTABLE = bool(EXE_DIR) and os.path.exists(os.path.join(EXE_DIR, "portable.txt"))
CONFIG_DIR = os.path.join(EXE_DIR, "data") if PORTABLE else os.path.join(APPDATA, "Nullpoint")
OLD_DIR = os.path.join(APPDATA, "CrosshairOverlay")  # name before the Nullpoint rename
DEFAULT_UPDATE_REPO = "yensobased1/nullpoint"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# Every crosshair setting. Share codes encode exactly this dict (see share_code.py).
DEFAULT_CROSSHAIR = {
    "mode": "lines",  # "lines", "png" or "text"
    "color": "00FFFF",
    "outline": {"on": True, "thick": 1, "alpha": 0.5},
    "dot": {"on": True, "size": 2, "alpha": 1.0},
    "inner": {"on": True, "len": 6, "thick": 2, "gap": 3, "alpha": 0.8, "vsep": False, "vlen": 6},
    "outer": {"on": False, "len": 2, "thick": 2, "gap": 10, "alpha": 0.35, "vsep": False, "vlen": 2},
    "png": {"scale": 100, "alpha": 1.0, "rot": 0},
    "shape": "cross",  # cross / t / dot / circle / square / chevron / x / hexagon / triangle / diamond / plus
    "rot": 0,  # line rotation 0-90 degrees
    "ring": {"on": False, "radius": 10, "thick": 1, "alpha": 1.0, "gaps": 0, "gapsize": 20, "gaprot": 0},
    "colors": {"same": True, "lines": "00FFFF", "dot": "00FFFF", "ring": "00FFFF", "outline": "000000"},
    "rainbow": {"on": False, "speed": 5, "sat": 1.0},
    "shadow": {"on": False, "size": 2, "alpha": 0.5},  # soft dark halo under the outline
    "gradient": {"on": False, "c2": "FFFFFF"},  # lines: main/lines color at the center -> c2 at the tips
    "style": {"kind": "solid", "dash": 4, "gap": 2},  # solid / dashed / dotted
    "text": {"chars": "+", "font": "", "size": 24, "bold": True, "alpha": 1.0},  # mode "text"
}

DEFAULT_PROFILE = {
    "crosshair": DEFAULT_CROSSHAIR, "png_path": "", "offset_x": 0, "offset_y": 0,
    "monitor": 0,  # 0 = follow game window, N = monitor N
    "stretch": {"on": False, "w": 1440, "h": 1080, "native_w": 0},  # in-game res; native_w 0 = auto
    "anim_paused": False,
}

# Built-in games: process name (lowercase) -> profile. javaw.exe also needs "minecraft" in the title.
BUILTIN_GAMES = {
    "fortniteclient-win64-shipping.exe": "Fortnite",
    "valorant-win64-shipping.exe": "VALORANT",
    "cs2.exe": "Counter-Strike 2",
    "r5apex.exe": "Apex Legends",
    "r5apex_dx12.exe": "Apex Legends",
    "overwatch.exe": "Overwatch 2",
    "robloxplayerbeta.exe": "Roblox",
    "javaw.exe": "Minecraft",
    "minecraft.windows.exe": "Minecraft",
    "cod.exe": "Call of Duty",
}
GAMES_VERSION = 2  # bump when BUILTIN_GAMES grows so old configs pick up new games

DEFAULT_CONFIG = {
    "profiles": {name: DEFAULT_PROFILE for name in ["Default", *BUILTIN_GAMES.values()]},
    "games": dict(BUILTIN_GAMES),
    "games_version": GAMES_VERSION,
    "active_profile": "Default",
    "visible": True,
    "show_only_in_games": True,  # UI: "Hide when game isn't focused"
    "fullscreen_mode": "Auto",  # Auto / Borderless / Exclusive
    # toggle/settings/switcher = global hotkeys; hold_hide/cheat = held keys (keyboard or Mouse2-5)
    "hotkeys": {"toggle": "F8", "settings": "F9", "switcher": "Alt+X", "hold_hide": "", "cheat": "F1"},
    "stream_safe": False,
    "theme": "System",  # System / Dark / Light
    "language": "en",  # en / ar
    "update_repo": DEFAULT_UPDATE_REPO,  # "owner/repo" on GitHub, empty = no update check
    "last_update_check": 0,
    "register_links": True,  # handle nullpoint://import/<code> links (per-user registry, no admin)
    "stream_page": {"on": False, "port": 7373},  # local page for OBS browser sources, 127.0.0.1 only
    "discord_rpc": False,
    "discord_client_id": "",
    "low_power": "Auto",  # Auto (on battery) / On / Off: slower polling, animations paused
    "edpi_saved": [],
    "wizard_done": False,
    "last_version": "",  # shows the changelog once after an update
    "ui_scale": 100,  # settings text scale: 100 / 125 / 150
    "large_text": False,
}


def merge(defaults, data):
    """Return defaults overlaid with data: missing keys get defaults, unknown keys are kept as-is."""
    out = copy.deepcopy(defaults)
    if not isinstance(data, dict):
        return out
    for k, v in data.items():
        d = out.get(k)
        if k in out and isinstance(d, dict) and isinstance(v, dict):
            out[k] = merge(d, v)
        elif k in out and not same_kind(d, v):
            continue  # wrong type in file: keep default
        else:
            out[k] = v
    return out


def same_kind(default, value):
    if isinstance(default, dict):
        return False
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str)
    return True


def clean_crosshair(cross):
    """Clamp every crosshair value to its valid range by round-tripping through the share code."""
    from share_code import ShareCodeError, export_code, import_code
    try:
        return import_code(export_code(merge(DEFAULT_CROSSHAIR, cross)))
    except (ShareCodeError, KeyError, TypeError, ValueError):
        return copy.deepcopy(DEFAULT_CROSSHAIR)


def fix_profiles(cfg):
    """Fill every profile with missing defaults (profiles are a dynamic dict, so merge() alone can't)."""
    profiles = cfg["profiles"] if isinstance(cfg.get("profiles"), dict) else {}
    cfg["profiles"] = {str(name)[:60]: merge(DEFAULT_PROFILE, p) for name, p in profiles.items()}
    for p in cfg["profiles"].values():
        p["crosshair"] = clean_crosshair(p["crosshair"])
        p["monitor"] = max(0, int(p["monitor"]))
    cfg["profiles"].setdefault("Default", copy.deepcopy(DEFAULT_PROFILE))
    if cfg["active_profile"] not in cfg["profiles"]:
        cfg["active_profile"] = "Default"
    cfg["games"] = {str(k).lower(): v for k, v in cfg["games"].items() if v in cfg["profiles"]}
    return cfg


def migrate_old_folder():
    """First start after the rename: copy %APPDATA%\\CrosshairOverlay (config, library, custom images) to
    %APPDATA%\\Nullpoint and point saved image paths at the copies. The old folder is left untouched."""
    if PORTABLE or os.path.exists(CONFIG_DIR) or not os.path.isdir(OLD_DIR):
        return False
    shutil.copytree(OLD_DIR, CONFIG_DIR)
    old_prefix = os.path.normcase(os.path.join(OLD_DIR, ""))

    def moved(path):
        if isinstance(path, str) and os.path.normcase(path).startswith(old_prefix):
            return os.path.join(CONFIG_DIR, path[len(old_prefix):])
        return path

    for name in ("config.json", "library.json"):
        path = os.path.join(CONFIG_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if name == "config.json" and isinstance(data, dict):
            for p in (data.get("profiles") or {}).values():
                if isinstance(p, dict):
                    p["png_path"] = moved(p.get("png_path", ""))
            if not data.get("update_repo"):
                data["update_repo"] = DEFAULT_UPDATE_REPO
        elif isinstance(data, list):
            for e in data:
                if isinstance(e, dict):
                    e["image"] = moved(e.get("image", ""))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return True


def load():
    if not os.path.exists(CONFIG_PATH):
        return fix_profiles(copy.deepcopy(DEFAULT_CONFIG))
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return normalize(json.load(f))
    except Exception:
        backup = CONFIG_PATH + time.strftime(".corrupt-%Y%m%d-%H%M%S.bak")
        try:
            os.replace(CONFIG_PATH, backup)
        except OSError:
            pass
        return fix_profiles(copy.deepcopy(DEFAULT_CONFIG))


def normalize(data):
    """Any parsed config (file or import) -> complete valid config. Raises on hopeless input."""
    if not isinstance(data, dict):
        raise ValueError("config must be an object")
    # User's own profiles replace the default list instead of merging with it.
    cfg = merge({k: v for k, v in DEFAULT_CONFIG.items() if k not in ("profiles", "games")}, data)
    cfg.setdefault("profiles", {})
    cfg.setdefault("games", {})
    if data.get("games_version", 1) < GAMES_VERSION:  # old config: add new built-in games once
        for exe, prof in BUILTIN_GAMES.items():
            cfg["games"].setdefault(exe, prof)
            cfg["profiles"].setdefault(prof, copy.deepcopy(DEFAULT_PROFILE))
        cfg["games_version"] = GAMES_VERSION
    return fix_profiles(cfg)


def save(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)  # atomic: a crash mid-write never corrupts the real file
