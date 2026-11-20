"""Share card PNG, QR encode/decode, nullpoint:// links, community gallery fetch."""
import json
import os
import re
import sys
import threading
import time
import urllib.request
import winreg
from urllib.parse import unquote

from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter

import overlay
import cs2
import valorant
from share_code import ShareCodeError, import_code
from ui.i18n import tr

PROTOCOL = "nullpoint"
LINK_PREFIX = "nullpoint://import/"
CODE_RE = re.compile(r"XH\d;[A-Za-z0-9;:,.%_\-]{1,600}")  # only share-code characters, nothing else
VAL_RE = re.compile(r"0;[A-Za-z0-9;.]{1,1000}")  # VALORANT crosshair code
GALLERY_URL = "https://raw.githubusercontent.com/yensobased1/nullpoint/main/gallery/index.json"
SUBMIT_URL = "https://github.com/yensobased1/nullpoint/issues/new"
DATE_RE = re.compile(r"20\d\d-[01]\d-[0-3]\d")


def submit_url(name, code):
    """Prefilled 'gallery submission' issue form. Only opened in the browser; you review and submit it yourself."""
    from urllib.parse import urlencode
    q = {"template": "gallery-submission.yml", "title": f"Gallery: {name[:40]}", "name": name[:40], "code": code}
    return SUBMIT_URL + "?" + urlencode(q)


def asset(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", name)


# ---------- QR ----------
def qr_image(text, cell=6, border=2):
    import qrcode
    qr = qrcode.QRCode(border=border)
    qr.add_data(text)
    qr.make(fit=True)
    m = qr.get_matrix()
    img = QImage(len(m) * cell, len(m) * cell, QImage.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    for y, row in enumerate(m):
        for x, on in enumerate(row):
            if on:
                p.fillRect(x * cell, y * cell, cell, cell, QColor("black"))
    p.end()
    return img


def decode_qr(img):
    """QImage -> first share code found in it, or raise ShareCodeError with a clear message."""
    import zxingcpp
    if img is None or img.isNull():
        raise ShareCodeError(tr("That is not an image."))
    g = img.convertToFormat(QImage.Format_Grayscale8)
    w, h, bpl = g.width(), g.height(), g.bytesPerLine()
    raw = bytes(g.constBits())[:bpl * h]
    data = b"".join(raw[y * bpl:y * bpl + w] for y in range(h))
    texts = [r.text for r in zxingcpp.read_barcodes(zxingcpp.ImageView(data, w, h, zxingcpp.ImageFormat.Lum))]
    for t in texts:
        m = CODE_RE.search(t)
        if m:
            import_code(m.group(0))  # validates; raises ShareCodeError
            return m.group(0)
        m = cs2.CODE_RE.search(t)
        if m:
            cs2.decode(m.group(0))  # validates (checksum)
            return m.group(0)
        t = re.sub(r"\s+", "", t)
        if VAL_RE.fullmatch(t):
            valorant.convert(t)  # validates
            return t
    raise ShareCodeError(tr("No Nullpoint QR code found in that image.") if not texts
                         else tr("The QR code doesn't contain a Nullpoint share code."))


# ---------- share card ----------
def share_card(cross, code, pixmap=None):
    """1200x630 black-and-white card: zoomed pixel-sharp crosshair, QR, share code, logo."""
    W, H = 1200, 630
    card = QImage(W, H, QImage.Format_ARGB32)
    card.fill(QColor("#000000"))
    p = QPainter(card)
    p.setPen(QColor("#2e2e2e"))
    p.drawRect(24, 24, W - 49, H - 49)
    # corner brackets like the banners
    L, T, R, B, n, t = 40, 40, W - 40, H - 40, 24, 4
    for x, y, vx, vy in ((L, T, L, T), (R - n, T, R - t, T), (L, B - t, L, B - n), (R - n, B - t, R - t, B - n)):
        p.fillRect(x, y, n, t, QColor("white"))
        p.fillRect(vx, vy, t, n, QColor("white"))
    c = overlay.extent(cross, pixmap)
    from preview import render_image
    img = render_image(lambda pp, cc: overlay.render(pp, cross, cc, pixmap), c)
    box = 360
    z = max(1, box // img.width())
    p.fillRect(QRect(80, 110, box, box), QColor("#151515"))
    p.drawImage(QRect(80 + (box - img.width() * z) // 2, 110 + (box - img.height() * z) // 2,
                      img.width() * z, img.height() * z), img)  # nearest-neighbour: sharp pixels
    logo = QImage(asset("nullpoint_128.png"))
    if not logo.isNull():
        p.drawImage(QRect(500, 110, 72, 72), logo)
    p.setPen(QColor("white"))
    f = QFont("Consolas")
    f.setPixelSize(54)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRect(592, 110, 560, 72), Qt.AlignVCenter | Qt.AlignLeft, "NULLPOINT")
    f.setPixelSize(20)
    f.setBold(False)
    p.setFont(f)
    p.setPen(QColor("#bdbdbd"))
    p.drawText(QRect(500, 200, 400, 30), Qt.AlignLeft, tr("Crosshair share code"))
    p.setPen(QColor("white"))
    f.setPixelSize(17)
    p.setFont(f)
    p.drawText(QRect(500, 236, 400, 250), Qt.TextWrapAnywhere | Qt.AlignLeft | Qt.AlignTop, code)
    qr = qr_image(code, cell=4)
    side = min(220, qr.width())
    p.drawImage(QRect(W - 80 - side, H - 80 - side, side, side), qr)
    p.setPen(QColor("#8c8c8c"))
    f.setPixelSize(16)
    p.setFont(f)
    p.drawText(QRect(80, H - 90, 600, 30), Qt.AlignLeft, "github.com/yensobased1/nullpoint")
    p.end()
    return card


# ---------- nullpoint:// links ----------
def share_card_frames(cross, code, path, max_frames=100):
    """Animated share card for a GIF crosshair: ([cards], [delays ms]). Decoded with the safe image limits."""
    import safe_image
    from PySide6.QtGui import QImageReader
    safe_image.check_file(path)
    reader = QImageReader(path)
    safe_image.read_qimage(QImageReader(path))  # size / frame-count checks
    frames, delays = [], []
    while len(frames) < max_frames:
        img = reader.read()
        if img.isNull():
            break
        frames.append(share_card(cross, code, overlay.transform_image(img, cross["png"])))
        delays.append(max(20, reader.nextImageDelay() or 100))
        if not reader.canRead():
            break
    return frames, delays


def discord_snippet(name, code):
    """A ready-to-paste Discord message: name, code block, import link, repo."""
    from urllib.parse import quote
    name = name.replace("`", "'").replace("*", "")[:60]
    return (f"**{name}** - Nullpoint crosshair\n```\n{code}\n```\n"
            f"Import: {LINK_PREFIX}{quote(code, safe='')}\nhttps://github.com/yensobased1/nullpoint")


def code_from_link(text):
    """Strictly extract a share code from nullpoint://import/<code>. Anything else -> None."""
    text = (text or "").strip().strip('"')
    if not text.lower().startswith(LINK_PREFIX):
        return None
    raw = text[len(LINK_PREFIX):].strip().rstrip("/")
    code = raw if ";" in raw else unquote(raw)  # a fully %-encoded link has no bare ';'; never decode twice
    try:
        if VAL_RE.fullmatch(code):
            valorant.convert(code)
        elif cs2.CODE_RE.fullmatch(code):
            cs2.decode(code)
        elif CODE_RE.fullmatch(code):
            import_code(code)
        else:
            return None
    except ShareCodeError:
        return None
    return code


def register_protocol(command):
    """Per-user (HKCU, no admin) handler: nullpoint://... -> `command "%1"`."""
    base = rf"Software\Classes\{PROTOCOL}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "URL:Nullpoint crosshair")
        winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'{command} "%1"')


def unregister_protocol():
    for sub in (r"\shell\open\command", r"\shell\open", r"\shell", ""):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{PROTOCOL}{sub}")
        except OSError:
            pass


# ---------- community gallery ----------
class Gallery(QObject):
    """Fetches gallery/index.json over HTTPS when asked; 1 hour cache on disk."""
    loaded = Signal(list, str)  # (entries, error message or "")

    def __init__(self, cache_path):
        super().__init__()
        self.cache_path = cache_path

    def fetch(self):
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                cached = json.load(f)
            if time.time() - cached.get("time", 0) < 3600:
                self.loaded.emit(self.clean(cached.get("entries")), "")
                return
        except (OSError, ValueError, AttributeError):
            pass
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            req = urllib.request.Request(GALLERY_URL, headers={"User-Agent": "Nullpoint-gallery"})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read(1_000_000).decode("utf-8"))
            entries = self.clean(data.get("entries") if isinstance(data, dict) else None)
            try:
                with open(self.cache_path, "w", encoding="utf-8") as f:
                    json.dump({"time": time.time(), "entries": entries}, f)
            except OSError:
                pass
            self.loaded.emit(entries, "")
        except Exception:
            self.loaded.emit([], tr("Couldn't reach the gallery. Check your internet connection and try again."))

    @staticmethod
    def clean(entries):
        """Untrusted data: keep only entries with a valid share code, short text fields."""
        out = []
        for e in entries[:500] if isinstance(entries, list) else []:
            if not isinstance(e, dict) or not isinstance(e.get("code"), str) or not CODE_RE.fullmatch(e["code"]):
                continue
            try:
                import_code(e["code"])
            except ShareCodeError:
                continue
            tags = e.get("tags") if isinstance(e.get("tags"), list) else []
            added = e.get("added") if isinstance(e.get("added"), str) and DATE_RE.fullmatch(e["added"]) else ""
            out.append({"name": str(e.get("name", "Crosshair"))[:40], "author": str(e.get("author", ""))[:40],
                        "tags": [str(t)[:20] for t in tags][:8], "code": e["code"], "added": added})
        return out
