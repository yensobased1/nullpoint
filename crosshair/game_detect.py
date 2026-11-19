"""Foreground window detection via plain Win32 queries (no hooks, no process memory reads)."""
import ctypes
import os
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
user32.GetForegroundWindow.restype = wintypes.HWND
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
user32.IsIconic.argtypes = [wintypes.HWND]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MONITOR_DEFAULTTONEAREST = 2
QUNS_RUNNING_D3D_FULL_SCREEN = 3


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_names = {}  # pid -> exe name cache, so we open each process only once


def process_name(pid):
    if pid in _names:
        return _names[pid]
    name = ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            name = os.path.basename(buf.value).lower()
        kernel32.CloseHandle(h)
    if len(_names) > 256:
        _names.clear()
    _names[pid] = name
    return name


def foreground():
    """-> (hwnd, pid, exe_name) of the focused window, or (None, 0, '')."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, 0, ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return hwnd, pid.value, process_name(pid.value)


def client_center(hwnd):
    """Center pixel of the window's client area in physical screen coords, or None if minimized/empty."""
    r = wintypes.RECT()
    if user32.IsIconic(hwnd) or not user32.GetClientRect(hwnd, ctypes.byref(r)) or r.right <= 0 or r.bottom <= 0:
        return None
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x + r.right // 2, pt.y + r.bottom // 2


def monitor_center(hwnd):
    mon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    user32.GetMonitorInfoW(mon, ctypes.byref(mi))
    r = mi.rcMonitor
    return r.left + (r.right - r.left) // 2, r.top + (r.bottom - r.top) // 2


def exclusive_fullscreen():
    """True when Windows reports a D3D exclusive-fullscreen app in front."""
    state = ctypes.c_int()
    return shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0 and \
        state.value == QUNS_RUNNING_D3D_FULL_SCREEN


user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
TITLE_REQUIRED = {"javaw.exe": "minecraft"}  # shared launchers: only count as a game with this in the title


def window_title(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def match_game(games, exe, hwnd):
    """Profile name for this foreground window, or None if it isn't a known game."""
    prof = games.get(exe)
    need = TITLE_REQUIRED.get(exe)
    if prof and need and need not in window_title(hwnd).lower():
        return None
    return prof
