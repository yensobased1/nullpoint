"""Small on-screen windows: hotkey cheat sheet card (click-through) and the quick switcher."""
import ctypes

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QGridLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ui.i18n import tr

user32 = ctypes.windll.user32
user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]


class InfoCard(QWidget):
    """Black/white card listing lines of text. Click-through, never takes focus."""

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.lines = []

    def show_lines(self, title, lines, center):
        self.title, self.lines = title, lines
        f = QFont(self.font())
        f.setPointSize(11)
        self.setFont(f)
        w = 40 + max(self.fontMetrics().horizontalAdvance(t) for t in [title] + lines)
        h = 54 + 24 * len(lines)
        self.setGeometry(center[0] - w // 2, center[1] - h // 2, w, h)
        self.show()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(0, 0, 0, 225))
        p.setPen(QColor(255, 255, 255, 90))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)
        p.setPen(QColor("white"))
        bold = QFont(self.font())
        bold.setBold(True)
        p.setFont(bold)
        p.drawText(QRect(20, 12, self.width() - 40, 24), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setFont(self.font())
        for i, line in enumerate(self.lines):
            p.drawText(QRect(20, 42 + 24 * i, self.width() - 40, 24), Qt.AlignLeft | Qt.AlignVCenter, line)


class QuickSwitcher(QWidget):
    """Up to 8 favorites in a grid; 1-8 or click to pick, Esc closes. Gives focus back right after."""
    picked = Signal(int)

    def __init__(self, entries, icons, center, prev_hwnd):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.prev_hwnd = prev_hwnd
        self.setStyleSheet("QWidget { background: #000; color: #fff; } QToolButton { border: 1px solid #444;"
                           " border-radius: 4px; padding: 4px; } QToolButton:focus, QToolButton:hover"
                           " { border-color: #fff; }")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(tr("Quick switch: press 1-8, Esc to close")))
        grid = QGridLayout()
        lay.addLayout(grid)
        if not entries:
            lay.addWidget(QLabel(tr("Star crosshairs in the Library to add them here.")))
        for i, (e, ic) in enumerate(zip(entries[:8], icons)):
            b = QToolButton()
            b.setIcon(ic)
            b.setIconSize(QSize(56, 56))
            b.setText(f"{i + 1}  {e['name'][:14]}")
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setAccessibleName(e["name"])
            b.clicked.connect(lambda _=False, i=i: self.pick(i))
            grid.addWidget(b, i // 4, i % 4)
        self.count = min(8, len(entries))
        self.adjustSize()
        self.move(center[0] - self.width() // 2, center[1] - self.height() // 2)

    def keyPressEvent(self, e):
        n = e.key() - Qt.Key_1
        if 0 <= n < self.count:
            self.pick(n)
        elif e.key() == Qt.Key_Escape:
            self.close()

    def pick(self, i):
        self.picked.emit(i)
        self.close()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == e.Type.ActivationChange and not self.isActiveWindow() and self.isVisible():
            self.close()  # clicked elsewhere: go away

    def closeEvent(self, e):
        if self.prev_hwnd:
            user32.SetForegroundWindow(self.prev_hwnd)  # hand focus straight back to the game
        super().closeEvent(e)
