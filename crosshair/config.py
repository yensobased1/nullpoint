"""Load/save config JSON in %APPDATA%\\Nullpoint\\config.json."""
import copy
import json
import os
import re
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
BACKUP_DIR = os.path.join(CONFIG_DIR, "backups")
MAX_BACKUPS = 10
MAX_JSON = 5 * 1024 * 1024
REPAIRED = []  # (file name, backup it came from or "") per repaired file; the app shows these once

# Every crosshair setting. Share codes encode exactly this dict (see share_code.py).
DEFAULT_CROSSHAIR = {
    "mode": "lines",  # "lines", "png" or "text"
    "color": "00FFFF",
    "outline": {"on": True, "thick": 1, "alpha": 0.5},
    "dot": {"on": True, "size": 2, "alpha": 1.0, "shape": "square"},  # square / circle / diamond
    "inner": {"on": True, "len": 6, "thick": 2, "gap": 3, "alpha": 0.8, "vsep": False, "vlen": 6},
    "outer": {"on": False, "len": 2, "thick": 2, "gap": 10, "alpha": 0.35, "vsep": False, "vlen": 2},
    "png": {"scale": 100, "alpha": 1.0, "rot": 0},
    "shape": "cross",  # cross / t / dot / circle / square / chevron / x / hexagon / triangle / diamond / plus
    "rot": 0,  # line rotation 0-90 degrees
    "ring": {"on": False, "radius": 10, "thick": 1, "alpha": 1.0, "gaps": 0, "gapsize": 20, "gaprot": 0},
    "colors": {"same": True, "lines": "00FFFF", "dot": "00FFFF", "ring": "00FFFF", "outline": "000000"},
    "rainbow": {"on": False, "speed": 5, "sat": 1.0},
    # Soft halo under the outline: mode "shadow" (black) or "glow" (color). size = radius px, alpha = intensity.
    "shadow": {"on": False, "size": 2, "alpha": 0.5, "mode": "shadow", "color": "FFFFFF"},
    "gradient": {"on": False, "c2": "FFFFFF"},  # lines: main/lines color at the center -> c2 at the tips
    "style": {"kind": "solid", "dash": 4, "gap": 2},  # solid / dashed / dotted
    "text": {"chars": "+", "font": "", "size": 24, "bold": True, "alpha": 1.0},  # mode "text"
    # Per-arm inner length (t/r/b/l) and arm color (ct.., "" = lines color). Used only when link is off.
    "arms": {"link": True, "t": 6, "r": 6, "b": 6, "l": 6, "ct": "", "cr": "", "cb": "", "cl": ""},
    # Fire expand: while left mouse is held in a game, line gaps grow by px over ms. Visual only.
    "expand": {"on": False, "px": 4, "ms": 120},
}

DEFAULT_PROFILE = {
    "crosshair": DEFAULT_CROSSHAIR, "png_path": "", "offset_x": 0, "offset_y": 0,
    "monitor": 0,  # 0 = follow game window, N = monitor N
    "stretch": {"on": False, "w": 1440, "h": 1080, "native_w": 0},  # in-game res; native_w 0 = auto
    "anim_paused": False,
    # Per game-window-resolution crosshairs: {"2560x1440": crosshair, ...}. No match = "crosshair" above.
    "variants": {},
}
RES_KEY = re.compile(r"[1-9][0-9]{2,4}x[1-9][0-9]{2,4}")
MAX_VARIANTS = 8
MAX_RULES = 50
RULE_MATCH = ("contains", "exact", "regex")

# Built-in games: process name (lowercase) -> display name. Detected as games (crosshair centered on their window,
# shown when "only in games" is on) without a profile of their own. javaw.exe also needs "minecraft" in the title.
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
    "project8.exe": "Deadlock",
}
GAMES_VERSION = 4  # bump when BUILTIN_GAMES grows so old configs pick up new games
MAX_GAMES = 200

DEFAULT_CONFIG = {
    "profiles": {"Default": DEFAULT_PROFILE},
    "games": dict.fromkeys(BUILTIN_GAMES, ""),  # exe -> profile name, "" = keep the profile you picked
    "game_offsets": {},  # exe -> [x, y] px added while that game is focused (games whose crosshair isn't centered)
    "games_version": GAMES_VERSION,
    "active_profile": "Default",
    "visible": True,
    "show_only_in_games": True,  # UI: "Hide when game isn't focused"
    "hide_in_menus": False,  # hide while the game shows the mouse cursor (lobby / menus)
    "fullscreen_mode": "Auto",  # Auto / Borderless / Exclusive
    # toggle/settings/switcher = global hotkeys; hold_hide/cheat = held keys (keyboard or Mouse2-5)
    "hotkeys": {"toggle": "F8", "settings": "F9", "switcher": "Alt+X", "hold_hide": "", "cheat": "F1",
                "nudge": ""},  # nudge: off by default; arrow keys move the crosshair until Esc
    # Profile rules, tested in order before the process list: exe and/or window title (contains / exact / regex).
    "rules": [],
    "hdr": {"mode": "Off", "mult": 1.5},  # Off / Manual / Auto (when Windows HDR is on for that monitor)
    "startup_delay": 0,  # seconds to wait before showing the overlay when started with Windows
    "stream_safe": False,
    "theme": "System",  # System / Dark / Light
    "language": "en",  # en / ar
    "update_repo": DEFAULT_UPDATE_REPO,  # "owner/repo" on GitHub, empty = no update check
    "last_update_check": 0,
    "beta_updates": False,  # also offer GitHub pre-releases
    "register_links": True,  # handle nullpoint://import/<code> links (per-user registry, no admin)
    # Local page for OBS browser sources: 127.0.0.1 only, URL needs the random token (made on first use).
    "stream_page": {"on": False, "port": 7373, "token": "", "theme": "dark", "pos": "top-left", "size": 96,  # nosec B105 - token "" = make one on load
                    "code": True, "qr": False, "name": True},
    # Twitch !crosshair (opt-in). The token is in Windows Credential Manager, never here.
    "twitch": {"on": False, "channel": "", "cooldown": 30},
    "discord_rpc": False,
    "discord_client_id": "",
    "low_power": "Auto",  # Auto (on battery) / On / Off: slower polling, animations paused
    "edpi_saved": [],
    "wizard_done": False,
    "last_version": "",  # shows the changelog once after an update
    "ui_scale": 100,  # settings text scale: 100 / 125 / 150
    "large_text": False,
    # VALORANT draws its crosshair in raw pixels (no resolution scaling), so imports are 1:1 by default.
    # On = scale by screen height / 1080 to keep the look you had at 1080p.
    "valorant_scale_1080": False,
    "reduce_motion": False,  # no rainbow, GIF playback or fire-expand animation
    "recent": [],  # last 5 applied crosshairs for the tray menu: {"name", "code", "image"}
    "clipboard_watch": False,  # offer to import codes you copy (opt-in; clipboard text is never stored)
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
        v = p["variants"] if isinstance(p["variants"], dict) else {}
        p["variants"] = {k: clean_crosshair(c) for k, c in list(v.items())[:MAX_VARIANTS]
                         if isinstance(k, str) and RES_KEY.fullmatch(k) and isinstance(c, dict)}
    cfg["profiles"].setdefault("Default", copy.deepcopy(DEFAULT_PROFILE))
    if cfg["active_profile"] not in cfg["profiles"]:
        cfg["active_profile"] = "Default"
    games = cfg["games"] if isinstance(cfg["games"], dict) else {}
    cfg["games"] = {str(k).lower()[:100]: (v if v in cfg["profiles"] else "") for k, v in list(games.items())[:MAX_GAMES]}
    offs = cfg["game_offsets"] if isinstance(cfg["game_offsets"], dict) else {}
    cfg["game_offsets"] = {}
    for k, v in list(offs.items())[:MAX_GAMES]:
        if isinstance(v, list) and len(v) == 2 and all(isinstance(n, (int, float)) and not isinstance(n, bool) for n in v):
            x, y = (min(max(round(n), -500), 500) for n in v)
            if x or y:
                cfg["game_offsets"][str(k).lower()[:100]] = [x, y]
    cfg["rules"] = clean_rules(cfg.get("rules"), cfg["profiles"])
    sp = cfg["stream_page"]
    if not re.fullmatch(r"[A-Za-z0-9_\-]{22,64}", str(sp["token"])):
        import secrets
        sp["token"] = secrets.token_urlsafe(24)
    from stream_server import POSITIONS, THEMES
    sp["theme"] = sp["theme"] if sp["theme"] in THEMES else "dark"
    sp["pos"] = sp["pos"] if sp["pos"] in POSITIONS else "top-left"
    sp["size"] = min(max(int(sp["size"]), 32), 256)
    sp["port"] = min(max(int(sp["port"]), 1024), 65535)
    tw = cfg["twitch"]
    tw["channel"] = tw["channel"].strip().lower()[:25] if re.fullmatch(r"\s*[A-Za-z0-9_]{0,25}\s*", tw["channel"]) else ""
    tw["cooldown"] = min(max(int(tw["cooldown"]), 5), 600)
    rec = cfg["recent"] if isinstance(cfg["recent"], list) else []
    cfg["recent"] = [{"name": str(r.get("name", ""))[:60], "code": str(r.get("code", ""))[:2048],
                      "image": str(r.get("image", ""))[:400]} for r in rec if isinstance(r, dict)][:5]
    cfg["startup_delay"] = min(max(int(cfg["startup_delay"]), 0), 120)
    if cfg["hdr"].get("mode") not in ("Off", "Manual", "Auto"):
        cfg["hdr"]["mode"] = "Off"
    cfg["hdr"]["mult"] = min(max(float(cfg["hdr"]["mult"]), 1.0), 3.0)
    return cfg


def clean_rules(rules, profiles):
    """Keep only well-formed rules: {exe, title, match, profile} with an existing profile and a safe regex."""
    from game_detect import safe_regex
    out = []
    for r in rules if isinstance(rules, list) else []:
        if not isinstance(r, dict):
            continue
        rule = {"exe": str(r.get("exe", "")).strip().lower()[:100], "title": str(r.get("title", ""))[:200],
                "match": r.get("match") if r.get("match") in RULE_MATCH else "contains",
                "profile": str(r.get("profile", ""))}
        if rule["profile"] not in profiles or not (rule["exe"] or rule["title"]):
            continue
        if rule["match"] == "regex" and rule["title"] and safe_regex(rule["title"]) is None:
            continue
        out.append(rule)
    return out[:MAX_RULES]


def active_cross(profile, res):
    """The profile's crosshair for this game resolution ("2560x1440"), or its default one."""
    return profile["variants"].get(res) or profile["crosshair"] if res else profile["crosshair"]


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


def defaults():
    return fix_profiles(copy.deepcopy(DEFAULT_CONFIG))


def read_json(path):
    if os.path.getsize(path) > MAX_JSON:
        raise ValueError("file too big")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def backups_of(path):
    """Backups of config.json / library.json, newest first."""
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        names = [n for n in os.listdir(BACKUP_DIR) if n.startswith(stem + "-") and n.endswith(".json")]
    except OSError:
        return []
    return [os.path.join(BACKUP_DIR, n) for n in sorted(names, reverse=True)]  # names sort by time


def backup(path):
    """Keep a copy of a file that just loaded fine (skipped if the newest backup is identical). Last 10 kept."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        old = backups_of(path)
        if old:
            with open(old[0], "rb") as f:
                if f.read() == data:
                    return
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0]
        ns = time.time_ns()  # one clock read, so names always sort in time order
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(ns // 10**9))
        dst = os.path.join(BACKUP_DIR, f"{stem}-{stamp}-{ns % 10**9:09d}.json")
        with open(dst + ".tmp", "wb") as f:
            f.write(data)
        os.replace(dst + ".tmp", dst)
        for extra in backups_of(path)[MAX_BACKUPS:]:
            os.remove(extra)
    except OSError:
        pass  # a missing backup must never stop the app


def repair(path, parse):
    """A damaged file: keep it as <file>.<time>.corrupt, then restore the newest backup that still parses.
    -> parsed data, or None when no backup works (the caller starts fresh)."""
    corrupt = f"{path}.{time.strftime('%Y%m%d-%H%M%S')}.corrupt"
    try:
        os.replace(path, corrupt)
    except OSError:
        pass
    for b in backups_of(path):
        try:
            data = parse(read_json(b))
            shutil.copyfile(b, path + ".tmp")
            os.replace(path + ".tmp", path)
        except (OSError, ValueError, TypeError, KeyError):
            continue
        REPAIRED.append((os.path.basename(path), os.path.basename(b)))
        return data
    REPAIRED.append((os.path.basename(path), ""))
    return None


def load():
    if not os.path.exists(CONFIG_PATH):
        return defaults()
    try:
        cfg = normalize(read_json(CONFIG_PATH), keep_old_profiles=True)
    except Exception:  # damaged / hand-edited badly: never crash, never silently lose settings
        return repair(CONFIG_PATH, lambda d: normalize(d, keep_old_profiles=True)) or defaults()
    backup(CONFIG_PATH)
    return cfg


def normalize(data, keep_old_profiles=False):
    """Any parsed config (file or import) -> complete valid config. Raises on hopeless input.
    keep_old_profiles: when upgrading from before 2.2, save removed game profiles' crosshairs to the library."""
    if not isinstance(data, dict):
        raise ValueError("config must be an object")
    # User's own profiles replace the default list instead of merging with it.
    cfg = merge({k: v for k, v in DEFAULT_CONFIG.items() if k not in ("profiles", "games")}, data)
    cfg.setdefault("profiles", {})
    cfg.setdefault("games", {})
    old = data.get("games_version", 1)
    if old < GAMES_VERSION:  # old config: add new built-in games once (as games, not profiles)
        for exe in BUILTIN_GAMES:
            cfg["games"].setdefault(exe, "")
        cfg["games_version"] = GAMES_VERSION
    cfg = fix_profiles(cfg)
    if old < 3:
        drop_builtin_profiles(cfg, keep_old_profiles)
    return cfg


def drop_builtin_profiles(cfg, keep=False):
    """2.2: games no longer get their own profile. The built-in game profiles (Fortnite, VALORANT, ...) are removed;
    their games keep the profile you pick. keep: crosshairs that differ from Default go to the library first."""
    old = []
    for name in dict.fromkeys(BUILTIN_GAMES.values()):
        p = cfg["profiles"].pop(name, None) if name != "Default" else None
        if p is None:
            continue
        cfg["games"] = {e: ("" if v == name else v) for e, v in cfg["games"].items()}
        if p["crosshair"] != cfg["profiles"]["Default"]["crosshair"]:
            old.append({"name": f"{name} (old profile)", "crosshair": p["crosshair"], "image": p["png_path"],
                        "tags": ["profile"], "fav": False})
    if keep and old:
        import library  # here, not at the top: library imports config
        entries = library.load()
        names = {e["name"] for e in entries}  # migration can run twice if the app quits before saving: no duplicates
        library.save(entries + [e for e in old if e["name"] not in names])
    if cfg["active_profile"] not in cfg["profiles"]:
        cfg["active_profile"] = "Default"
    cfg["rules"] = clean_rules(cfg["rules"], cfg["profiles"])


def save(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)  # atomic: a crash mid-write never corrupts the real file
