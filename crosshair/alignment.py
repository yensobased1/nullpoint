"""Full-screen alignment test: 1px grid, exact center lines, resolution. The overlay draws on top. Esc closes."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ui.i18n import tr


class AlignmentWindow(QWidget):
    closed = Signal()

    def __init__(self, screen):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)  # NOT topmost: the overlay stays above it
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.BlankCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#101214"))
        for step, col in ((10, QColor(255, 255, 255, 22)), (50, QColor(255, 255, 255, 55))):
            p.setPen(col)
            for x in range(w // 2 % step, w, step):
                p.drawLine(x, 0, x, h)
            for y in range(h // 2 % step, h, step):
                p.drawLine(0, y, w, y)
        # Pixel column w//2 / row h//2 = the overlay's center pixel (its left/top edge is the true center).
        p.setPen(QColor(255, 60, 60))
        p.drawLine(w // 2, 0, w // 2, h)
        p.drawLine(0, h // 2, w, h // 2)
        p.setPen(QColor("#e6e8eb"))
        p.drawText(20, 30, f"{w} x {h}   center pixel ({w // 2}, {h // 2})   " + tr("Esc to close"))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)
