"""Fullscreen help without touching the game.

A normal window (like this overlay) shows over "fullscreen" games when Windows' fullscreen optimizations (FSO) are
on: the game then runs as a borderless flip-model window. In true exclusive fullscreen nothing can draw over the
game except tools that hook DirectX, which anti-cheat bans, so Nullpoint never does that. Instead it:
- finds the per-game "Disable fullscreen optimizations" compatibility flag and can clear it (your user only, HKCU),
- notices when FSO is switched off for all games (GameConfigStore) and explains how to undo it,
- tells you which window mode to pick in the game's own settings.
"""
import winreg

LAYERS = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
FSO_FLAG = "DISABLEDXMAXIMIZEDWINDOWEDMODE"

# Process name -> the game's own name for its borderless mode (as shown in its video settings, in English).
GAME_MODES = {
    "fortniteclient-win64-shipping.exe": "Windowed Fullscreen",
    "valorant-win64-shipping.exe": "Windowed Fullscreen",
    "cs2.exe": "Fullscreen Windowed",
    "r5apex.exe": "Borderless Window",
    "r5apex_dx12.exe": "Borderless Window",
    "overwatch.exe": "Borderless Windowed",
    "cod.exe": "Fullscreen Borderless",
    "javaw.exe": "Windowed (F11 fullscreen is exclusive in some versions)",
}


def _flags(root, path, layers=LAYERS):
    try:
        with winreg.OpenKey(root, layers) as k:
            for i in range(10000):
                try:
                    name, value, _ = winreg.EnumValue(k, i)
                except OSError:
                    break
                if name.lower() == path.lower() and isinstance(value, str):
                    return name, value
    except OSError:
        pass
    return None, ""


def fso_disabled(exe_path, layers=LAYERS):
    """-> "user", "machine" or "" : where "Disable fullscreen optimizations" is set for this exe."""
    if not exe_path:
        return ""
    for root, where in ((winreg.HKEY_CURRENT_USER, "user"), (winreg.HKEY_LOCAL_MACHINE, "machine")):
        if FSO_FLAG in _flags(root, exe_path, layers)[1].upper().split():
            return where
    return ""


def enable_fso(exe_path, layers=LAYERS):
    """Remove only the FSO flag from this exe's compatibility settings for your user (other flags stay).
    Returns True if something changed. Machine-wide (HKLM) flags need the game's Properties > Compatibility."""
    name, value = _flags(winreg.HKEY_CURRENT_USER, exe_path, layers)
    if name is None:
        return False
    rest = [t for t in value.split() if t.upper() != FSO_FLAG]
    if len(rest) == len(value.split()):
        return False
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, layers, 0, winreg.KEY_SET_VALUE) as k:
        if [t for t in rest if t != "~"]:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, " ".join(rest))
        else:
            winreg.DeleteValue(k, name)  # only the "~" marker was left: same as no flags
    return True


def fso_off_for_all_games():
    """True when FSO is switched off system-wide (the GameDVR_FSEBehaviorMode = 2 tweak)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore") as k:
            return winreg.QueryValueEx(k, "GameDVR_FSEBehaviorMode")[0] == 2
    except OSError:
        return False
