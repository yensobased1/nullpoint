"""Secrets (the Twitch chat token) live in Windows Credential Manager, never in config.json, logs or reports."""
import ctypes
from ctypes import wintypes

advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
CRED_TYPE_GENERIC, CRED_PERSIST_LOCAL_MACHINE = 1, 2
PREFIX = "Nullpoint/"


class CREDENTIAL(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR)]


advapi32.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
advapi32.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
advapi32.CredFree.argtypes = [ctypes.c_void_p]


def save(name, secret):
    blob = secret.encode("utf-16-le")
    buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    cred = CREDENTIAL(Type=CRED_TYPE_GENERIC, TargetName=PREFIX + name, CredentialBlobSize=len(blob),
                      CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)), Persist=CRED_PERSIST_LOCAL_MACHINE,
                      UserName="Nullpoint")
    if not advapi32.CredWriteW(ctypes.byref(cred), 0):
        raise OSError(ctypes.get_last_error(), "Could not save to Windows Credential Manager")


def load(name):
    p = ctypes.POINTER(CREDENTIAL)()
    if not advapi32.CredReadW(PREFIX + name, CRED_TYPE_GENERIC, 0, ctypes.byref(p)):
        return ""
    try:
        c = p.contents
        return ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize).decode("utf-16-le")
    finally:
        advapi32.CredFree(p)


def delete(name):
    advapi32.CredDeleteW(PREFIX + name, CRED_TYPE_GENERIC, 0)
