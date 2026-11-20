"""Update check (once a day) and the in-app updater.

Check: newest GitHub release of the repo (pre-releases only with the beta channel), newer than this version only.
Install, only after you confirm: download the installer from the release (net.get: HTTPS, GitHub hosts only, size
limit) into a fresh private temp folder, check its SHA-256 against checksums.txt from the same release, lock the
file against changes, check the hash again on disk, then run it and quit. Any mismatch aborts.
"""
import ctypes
import hashlib
import json
import os
import re
import subprocess  # nosec B404 - only runs the verified installer, argument list, no shell
import tempfile
import threading
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

import net

VERSION = "2.2.1"
REPO_RE = re.compile(r"[\w.-]+/[\w.-]+")
INSTALLER_RE = re.compile(r"Nullpoint-Setup-\d+\.\d+\.\d+\.exe")
MAX_INSTALLER = 150 * 1024 * 1024
REQUIRE_SIGNATURE = False  # turn on once releases are Authenticode-signed (docs/SIGNING.md)


def version_tuple(text):
    return tuple(int(n) for n in re.findall(r"\d+", text)[:3])


def pick_release(releases, beta=False, current=VERSION):
    """Newest release that is newer than current (never a downgrade). Pre-releases only on the beta channel."""
    best = None
    for r in releases if isinstance(releases, list) else []:
        if not isinstance(r, dict) or r.get("draft") or (r.get("prerelease") and not beta):
            continue
        tag = str(r.get("tag_name", ""))
        if len(version_tuple(tag)) == 3 and version_tuple(tag) > version_tuple(current) and \
                (best is None or version_tuple(tag) > version_tuple(best["tag_name"])):
            best = r
    return best


def release_info(rel, repo):
    """GitHub release JSON -> what the app needs, or None. Download links must point at this repo's releases."""
    prefix = f"https://github.com/{repo}/releases/download/"
    assets = {a.get("name"): a.get("browser_download_url") for a in rel.get("assets", []) if isinstance(a, dict)}
    installer = next((n for n in assets if isinstance(n, str) and INSTALLER_RE.fullmatch(n)), None)
    page = str(rel.get("html_url", ""))
    if not page.startswith(f"https://github.com/{repo}/releases/"):
        return None
    info = {"version": str(rel["tag_name"])[:32], "url": page, "notes": str(rel.get("body") or "")[:20000],
            "installer": "", "installer_name": "", "checksums": ""}
    sums = assets.get("checksums.txt")
    if installer and str(assets[installer]).startswith(prefix) and str(sums).startswith(prefix):
        info.update(installer=assets[installer], installer_name=installer, checksums=sums)
    return info


def parse_checksums(text):
    """'<sha256>  <file name>' lines -> {file name: sha256}."""
    out = {}
    for line in text.splitlines():
        m = re.fullmatch(r"\s*([0-9a-fA-F]{64})\s+\*?(\S+)\s*", line)
        if m:
            out[m.group(2)] = m.group(1).lower()
    return out


class UpdateChecker(QObject):
    found = Signal(dict)  # release_info(...)

    def check(self, repo, beta=False):
        if REPO_RE.fullmatch(repo or ""):
            threading.Thread(target=self._run, args=(repo, beta), daemon=True).start()

    def _run(self, repo, beta):
        try:
            if beta:
                rels = json.loads(net.get(f"https://api.github.com/repos/{repo}/releases?per_page=20", 2 * 1024 * 1024))
            else:
                rels = [json.loads(net.get(f"https://api.github.com/repos/{repo}/releases/latest", 512 * 1024))]
            rel = pick_release(rels, beta)
            info = release_info(rel, repo) if rel else None
            if info:
                self.found.emit(info)  # queued to the GUI thread
        except Exception:  # nosec B110 - offline / no releases / rate limited: the check stays silent on purpose
            pass


class Downloader(QObject):
    done = Signal(str, str, str)  # (installer path, sha256, error message)

    def start(self, info):
        threading.Thread(target=self._run, args=(info,), daemon=True).start()

    def _run(self, info):
        try:
            sums = parse_checksums(net.get(info["checksums"], 64 * 1024).decode("utf-8", "replace"))
            expected = sums.get(info["installer_name"])
            if not expected:
                raise ValueError("The release has no checksum for the installer.")
            data = net.get(info["installer"], MAX_INSTALLER)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("The download doesn't match the release checksum. Nothing was installed.")
            folder = tempfile.mkdtemp(prefix="nullpoint-update-")  # fresh folder under your own user profile
            path = os.path.join(folder, info["installer_name"])
            with open(path, "xb") as f:
                f.write(data)
            self.done.emit(path, expected, "")
        except Exception as e:
            self.done.emit("", "", str(e) or "Download failed.")


# ---------- run the verified file ----------
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.HANDLE]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING = 0x80000000, 1, 3
INVALID = wintypes.HANDLE(-1).value


def run_verified(path, sha256, start=True):
    """Lock the file (others may read, not change or delete it), re-check the hash on disk, start it, unlock.
    Nothing can swap the file between the check and the start. Raises ValueError on any problem."""
    h = kernel32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None)
    if not h or h == INVALID:
        raise ValueError("Couldn't open the downloaded installer.")
    try:
        with open(path, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != sha256:
                raise ValueError("The installer changed after the download. Nothing was installed.")
        if REQUIRE_SIGNATURE and not signed(path):
            raise ValueError("The installer isn't signed by Nullpoint. Nothing was installed.")
        if start:
            subprocess.Popen([path], close_fds=True)  # nosec B603 - our verified installer, no shell, no user input
    finally:
        kernel32.CloseHandle(h)


def signed(path):
    """Windows Authenticode check (WinVerifyTrust). True = valid signature from a trusted publisher chain."""
    class FILE_INFO(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pcwszFilePath", wintypes.LPCWSTR), ("hFile", wintypes.HANDLE),
                    ("pgKnownSubject", ctypes.c_void_p)]

    class DATA(ctypes.Structure):
        _fields_ = [("cbStruct", wintypes.DWORD), ("pPolicyCallbackData", ctypes.c_void_p),
                    ("pSIPClientData", ctypes.c_void_p), ("dwUIChoice", wintypes.DWORD),
                    ("fdwRevocationChecks", wintypes.DWORD), ("dwUnionChoice", wintypes.DWORD),
                    ("pFile", ctypes.POINTER(FILE_INFO)), ("dwStateAction", wintypes.DWORD),
                    ("hWVTStateData", wintypes.HANDLE), ("pwszURLReference", wintypes.LPCWSTR),
                    ("dwProvFlags", wintypes.DWORD), ("dwUIContext", wintypes.DWORD),
                    ("pSignatureSettings", ctypes.c_void_p)]

    class GUID(ctypes.Structure):
        _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

    action = GUID(0x00AAC56B, 0xCD44, 0x11D0, (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
    fi = FILE_INFO(ctypes.sizeof(FILE_INFO), path, None, None)
    data = DATA(cbStruct=ctypes.sizeof(DATA), dwUIChoice=2, dwUnionChoice=1, pFile=ctypes.pointer(fi))
    return ctypes.windll.wintrust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data)) == 0
