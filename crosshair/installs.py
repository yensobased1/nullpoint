"""Find installed games from launcher files on this PC (read-only, local files and registry only).

Epic: %ProgramData%\\Epic\\EpicGamesLauncher\\Data\\Manifests\\*.item (JSON)
Riot: %ProgramData%\\Riot Games\\RiotClientInstalls.json (+ the default C:\\Riot Games folders)
Battle.net: Blizzard entries under the Windows "Uninstall" registry keys.
Every file is size-limited and type-checked; anything missing or odd is skipped silently.
"""
import glob
import json
import os
import re
import winreg

MAX_FILE = 1024 * 1024
MAX_MANIFESTS = 500
PROGRAMDATA = os.environ.get("ProgramData", r"C:\ProgramData")
RIOT_GAMES = {"valorant": ("VALORANT", "valorant-win64-shipping.exe"),
              "league of legends": ("League of Legends", "league of legends.exe")}
BLIZZARD_EXES = {"overwatch": "overwatch.exe", "diablo iv": "diablo iv.exe", "call of duty": "cod.exe"}
NOT_GAME = re.compile(r"launcher|uninst|crash|report|setup|update|agent|helper|redist|install", re.IGNORECASE)
EXE = re.compile(r"[^\\/:*?\"<>|]{1,100}\.exe", re.IGNORECASE)


def read_json(path):
    try:
        if os.path.getsize(path) > MAX_FILE:
            return None
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def clean(name, exe, source):
    name = str(name).strip()[:60]
    exe = os.path.basename(str(exe)).strip().lower()
    if name and EXE.fullmatch(exe):
        return {"name": name, "exe": exe, "source": source}
    return None


def epic(folder=None):
    folder = folder or os.path.join(PROGRAMDATA, "Epic", "EpicGamesLauncher", "Data", "Manifests")
    out = []
    for path in sorted(glob.glob(os.path.join(folder, "*.item")))[:MAX_MANIFESTS]:
        d = read_json(path)
        if isinstance(d, dict) and isinstance(d.get("DisplayName"), str) and isinstance(d.get("LaunchExecutable"), str):
            g = clean(d["DisplayName"], d["LaunchExecutable"], "Epic")
            if g:
                out.append(g)
    return out


def riot(path=None):
    d = read_json(path or os.path.join(PROGRAMDATA, "Riot Games", "RiotClientInstalls.json"))
    places = []
    if isinstance(d, dict):
        assoc = d.get("associated_client")
        if isinstance(assoc, dict):
            places += [k for k in assoc if isinstance(k, str)]
    places += [p for p in (r"C:\Riot Games\VALORANT", r"C:\Riot Games\League of Legends") if os.path.isdir(p)]
    found = {}
    for p in places:
        low = p.lower()
        for key, (name, exe) in RIOT_GAMES.items():
            if key in low:
                found[exe] = {"name": name, "exe": exe, "source": "Riot"}
    return list(found.values())


def _exe_in(folder):
    """Main .exe in a game folder (top level only, skips launchers / uninstallers)."""
    try:
        names = sorted(os.listdir(folder))[:200]
    except OSError:
        return None
    exes = [n for n in names if n.lower().endswith(".exe") and not NOT_GAME.search(n)]
    return exes[0] if exes else None


def battlenet():
    out = []
    roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for hive, path in roots:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            for i in range(2000):
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                try:
                    with winreg.OpenKey(root, sub) as k:
                        vals = {}
                        for v in ("Publisher", "DisplayName", "InstallLocation"):
                            try:
                                vals[v] = str(winreg.QueryValueEx(k, v)[0])[:300]
                            except OSError:
                                vals[v] = ""
                except OSError:
                    continue
                name = vals["DisplayName"]
                if "blizzard" not in vals["Publisher"].lower() or not name or "battle.net" in name.lower():
                    continue
                exe = next((e for key, e in BLIZZARD_EXES.items() if key in name.lower()), None)
                if not exe and vals["InstallLocation"]:
                    exe = _exe_in(vals["InstallLocation"])
                g = clean(name, exe or "", "Battle.net") if exe else None
                if g:
                    out.append(g)
    return out


def detect(known=()):
    """All detected games not already mapped (known = exe names in the config), one entry per exe."""
    seen, out = set(known), []
    for finder in (epic, riot, battlenet):
        try:
            games = finder()
        except Exception:  # a broken launcher install must never break the settings window
            games = []
        for g in games:
            if g["exe"] not in seen:
                seen.add(g["exe"])
                out.append(g)
    return out
