"""Key names -> Windows virtual keys. Global hotkeys use RegisterHotKey (press only);
hold keys (hide while held, cheat sheet) are polled with GetAsyncKeyState so the game still gets the key."""
import ctypes

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

user32 = ctypes.windll.user32
user32.GetAsyncKeyState.restype = ctypes.c_short
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 1, 2, 4, 8, 0x4000
SPECIAL_VK = {Qt.Key_Insert: 0x2D, Qt.Key_Delete: 0x2E, Qt.Key_Home: 0x24, Qt.Key_End: 0x23,
              Qt.Key_PageUp: 0x21, Qt.Key_PageDown: 0x22, Qt.Key_Pause: 0x13, Qt.Key_ScrollLock: 0x91,
              Qt.Key_Space: 0x20, Qt.Key_Tab: 0x09, Qt.Key_CapsLock: 0x14}
HOLD_NAMES = {"mouse2": 0x02, "mouse3": 0x04, "mouse4": 0x05, "mouse5": 0x06,
              "shift": 0x10, "ctrl": 0x11, "alt": 0x12}
HOLD_CHOICES = ["", "Mouse2", "Mouse3", "Mouse4", "Mouse5", "Shift", "Ctrl", "Alt", "F1", "Tab", "CapsLock"]


def to_win_hotkey(text):
    """'Ctrl+Shift+F8' -> (modifiers, virtual key) or None if unsupported."""
    seq = QKeySequence(text)
    if seq.count() == 0:
        return None
    combo = seq[0]
    key, mods = combo.key(), combo.keyboardModifiers()
    kv = key.value
    if Qt.Key_F1.value <= kv <= Qt.Key_F24.value:
        vk = 0x70 + kv - Qt.Key_F1.value
    elif Qt.Key_A.value <= kv <= Qt.Key_Z.value or Qt.Key_0.value <= kv <= Qt.Key_9.value:
        vk = kv  # same codes as Windows VKs
    elif key in SPECIAL_VK:
        vk = SPECIAL_VK[key]
    else:
        return None
    m = MOD_NOREPEAT
    for qt_mod, win_mod in ((Qt.ControlModifier, MOD_CONTROL), (Qt.AltModifier, MOD_ALT),
                            (Qt.ShiftModifier, MOD_SHIFT), (Qt.MetaModifier, MOD_WIN)):
        if mods & qt_mod:
            m |= win_mod
    return m, vk


def hold_vk(text):
    """'Mouse2' / 'Shift' / 'F1' / 'V' -> virtual key, or None (empty / unknown = off)."""
    name = (text or "").strip()
    if not name:
        return None
    if name.lower() in HOLD_NAMES:
        return HOLD_NAMES[name.lower()]
    hk = to_win_hotkey(name)
    return hk[1] if hk else None


def is_down(vk):
    """Reads only the current up/down state of this one key."""
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)
