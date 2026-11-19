"""HDR compensation: brighten the crosshair when Windows HDR ("advanced color") is on for its monitor.
Only asks Windows about the display (DisplayConfig API). Never reads the game image."""
import copy
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
QDC_ONLY_ACTIVE_PATHS = 2
GET_SOURCE_NAME, GET_ADVANCED_COLOR = 1, 9
MONITOR_DEFAULTTONEAREST = 2


class LUID(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.LONG)]


class PATH(ctypes.Structure):  # DISPLAYCONFIG_PATH_INFO (72 bytes)
    _fields_ = [("src_adapter", LUID), ("src_id", wintypes.UINT), ("src_mode", wintypes.UINT), ("src_flags", wintypes.UINT),
                ("tgt_adapter", LUID), ("tgt_id", wintypes.UINT), ("tgt_rest", wintypes.UINT * 9), ("flags", wintypes.UINT)]


class HEADER(ctypes.Structure):
    _fields_ = [("type", wintypes.UINT), ("size", wintypes.UINT), ("adapter", LUID), ("id", wintypes.UINT)]


class SOURCE_NAME(ctypes.Structure):
    _fields_ = [("header", HEADER), ("name", wintypes.WCHAR * 32)]


class ADVANCED_COLOR(ctypes.Structure):
    _fields_ = [("header", HEADER), ("value", wintypes.UINT), ("encoding", wintypes.UINT), ("bits", wintypes.UINT)]


class MONITORINFOEX(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]


def hdr_displays():
    """GDI names (\\\\.\\DISPLAY1 ...) of active displays with HDR / advanced color turned on."""
    n_paths, n_modes = wintypes.UINT(), wintypes.UINT()
    if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), ctypes.byref(n_modes)):
        return set()
    paths = (PATH * n_paths.value)()
    modes = (ctypes.c_byte * (64 * max(1, n_modes.value)))()
    if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), paths, ctypes.byref(n_modes), modes, None):
        return set()
    out = set()
    for p in paths[:n_paths.value]:
        col = ADVANCED_COLOR(HEADER(GET_ADVANCED_COLOR, ctypes.sizeof(ADVANCED_COLOR), p.tgt_adapter, p.tgt_id))
        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(col)) or not col.value & 2:  # bit 1 = enabled
            continue
        name = SOURCE_NAME(HEADER(GET_SOURCE_NAME, ctypes.sizeof(SOURCE_NAME), p.src_adapter, p.src_id))
        if not user32.DisplayConfigGetDeviceInfo(ctypes.byref(name)):
            out.add(name.name.lower())
    return out


def display_at(x, y):
    user32.MonitorFromPoint.restype = wintypes.HMONITOR
    mon = user32.MonitorFromPoint(wintypes.POINT(x, y), MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFOEX(cbSize=ctypes.sizeof(MONITORINFOEX))
    return mi.szDevice.lower() if user32.GetMonitorInfoW(mon, ctypes.byref(mi)) else ""


def is_hdr_at(x, y):
    try:
        return display_at(x, y) in hdr_displays()
    except (OSError, ValueError):
        return False


def multiplier(setting, x, y):
    """Config {"mode": Off / Manual / Auto, "mult": 1.0-3.0} -> brightness factor for the monitor at (x, y)."""
    mult = min(max(float(setting.get("mult", 1.0)), 1.0), 3.0)
    mode = setting.get("mode", "Off")
    if mode == "Manual" or (mode == "Auto" and is_hdr_at(x, y)):
        return mult
    return 1.0


HEX_KEYS = [("color",), ("colors", "lines"), ("colors", "dot"), ("colors", "ring"), ("colors", "outline"),
            ("gradient", "c2"), ("shadow", "color")] + [("arms", k) for k in ("ct", "cr", "cb", "cl")]
ALPHA_KEYS = ["outline", "dot", "inner", "outer", "ring", "text", "png", "shadow"]


def boost(cross, m):
    """Copy of the crosshair with colors and opacities multiplied by m (clamped). m = 1 returns it unchanged."""
    if m <= 1.0:
        return cross
    out = copy.deepcopy(cross)
    for path in HEX_KEYS:
        d = out
        for k in path[:-1]:
            d = d[k]
        v = d[path[-1]]
        if isinstance(v, str) and len(v) == 6:
            try:
                rgb = [min(255, round(int(v[i:i + 2], 16) * m)) for i in (0, 2, 4)]
                d[path[-1]] = "".join(f"{c:02X}" for c in rgb)
            except ValueError:
                pass
    for k in ALPHA_KEYS:
        out[k]["alpha"] = min(1.0, out[k]["alpha"] * m)
    return out
