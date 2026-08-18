#!/usr/bin/env python3
"""Karen OS Dock - macOS-style bottom bar: tile icons, magnification on hover,
tooltips, power menu. Premium look, negligible RAM (PyQt6, no compositor tricks).
"""

import subprocess, sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QRectF, QPoint
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMenu,
                             QVBoxLayout, QWidget)


def tile_pixmap(size, c1, c2, glyph, glyph_color="#F2F4FF", draw=None):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(1.5, 1.5, size - 3, size - 3)
    from PyQt6.QtGui import QLinearGradient, QBrush
    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0, QColor(c1))
    grad.setColorAt(1, QColor(c2))
    p.setBrush(QBrush(grad))
    p.setPen(QColor(255, 255, 255, 36))
    p.drawRoundedRect(r, 15, 15)
    if draw:
        draw(p, size)
    else:
        p.setPen(QColor(glyph_color))
        f = QFont("DejaVu Sans", int(size * 0.42))
        f.setBold(True)
        p.setFont(f)
        fm = QFontMetrics(f)
        p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, glyph)
    p.end()
    return pm


class Tile(QFrame):
    def __init__(self, name, tip, c1, c2, glyph=None, cmd=None, draw=None, power=False):
        super().__init__()
        self.tip, self.cmd, self.power = tip, cmd, power
        self.base = 52
        self.cur = self.base
        self.target = self.base
        self.setFixedSize(self.base, self.base)
        self.pm = tile_pixmap(self.base * 2, c1, c2, glyph, draw=draw)
        self.lbl = QLabel(self)
        self.lbl.setPixmap(self.pm.scaled(self.base, self.base,
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
        self.lbl.setGeometry(0, 0, self.base, self.base)
        self.tip_lbl = QLabel(tip)
        self.tip_lbl.setStyleSheet(
            "background:#1B2447;color:#FFFFFF;border:1px solid #E31C23;"
            "border-radius:7px;padding:3px 10px;font-size:11px;")
        self.tip_lbl.hide()
        self.tip_lbl.setParent(None)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._ease)
        self.timer.start(16)

    def _ease(self):
        if self.cur != self.target:
            self.cur += (self.target - self.cur) * 0.35
            if abs(self.cur - self.target) < 0.5:
                self.cur = self.target
            n = int(self.cur)
            self.setFixedSize(n, n)
            self.lbl.setPixmap(self.pm.scaled(n, n, Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))
            self.lbl.setGeometry(0, 0, n, n)
            if self.tip_lbl.isVisible():
                self._place_tip()

    def _place_tip(self):
        g = self.mapToGlobal(QPoint(0, 0))
        self.tip_lbl.adjustSize()
        self.tip_lbl.move(g.x() + (self.cur - self.tip_lbl.width()) // 2,
                          g.y() - self.tip_lbl.height() - 6)

    def enterEvent(self, e):
        self.target = int(self.base * 1.38)
        self._place_tip()
        self.tip_lbl.show()
        self.tip_lbl.raise_()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.target = self.base
        self.tip_lbl.hide()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.power:
                m = QMenu()
                m.setStyleSheet(
                    "QMenu{background:#0F1630;color:#F2F4FF;border:1px solid #E31C23;"
                    "border-radius:8px;padding:6px;} QMenu::item{padding:7px 22px;border-radius:5px;}"
                    "QMenu::item:selected{background:#E31C23;}")
                act_r = m.addAction("Reboot")
                act_s = m.addAction("Shutdown")
                ch = m.exec(e.globalPosition().toPoint())
                if ch == act_r:
                    subprocess.Popen(["systemctl", "reboot", "-i"])
                elif ch == act_s:
                    subprocess.Popen(["systemctl", "poweroff", "-i"])
            elif self.cmd:
                subprocess.Popen(["sh", "-c", self.cmd])
        super().mousePressEvent(e)


class Dock(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 10)
        lay.setSpacing(10)
        bar = QFrame()
        bar.setStyleSheet(
            "background:rgba(10,12,24,196);border:1px solid rgba(227,28,35,70);"
            "border-radius:22px;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 8, 14, 8)
        bl.setSpacing(10)
        bl.addWidget(Tile("term", "Terminal", "#1B2447", "#0F1630", ">_", "xterm"))
        bl.addWidget(Tile("files", "Files", "#E8983C", "#B06E1E", "",
                          "pcmanfm", draw=self._draw_folder))
        bl.addWidget(Tile("web", "Firefox", "#E8582C", "#A63A14", "Ff",
                          "firefox"))
        bl.addWidget(Tile("music", "Music", "#2FA24A", "#17602B", "♪",
                          "pcmanfm /opt/karen-linux/media"))
        bl.addWidget(Tile("notes", "Notes", "#4F7DFF", "#2C4AA0", "N",
                          "xterm -e 'nano /opt/karen-linux/notes.txt'"))
        bl.addWidget(Tile("set", "Settings", "#3A415C", "#232B4D", "s",
                          "xterm -e 'nano /etc/karen/config.json'"))
        bl.addWidget(Tile("pow", "Power", "#E31C23", "#8A0F14", "",
                          power=True, draw=self._draw_power))
        lay.addWidget(bar)
        self.adjustSize()
        self._pos()

    def _pos(self):
        app = QApplication.instance()
        screen = app.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2,
                  screen.bottom() - self.height() - 4)

    @staticmethod
    def _draw_folder(p, s):
        p.setBrush(QColor("#FFD9A0"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(int(s * 0.10), int(s * 0.38), int(s * 0.80), int(s * 0.42),
                          int(s * 0.06), int(s * 0.06))
        p.drawRoundedRect(int(s * 0.10), int(s * 0.38), int(s * 0.28), int(s * 0.10),
                          int(s * 0.05), int(s * 0.05))

    @staticmethod
    def _draw_power(p, s):
        from PyQt6.QtGui import QPen
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidthF(s * 0.07)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        r = s * 0.34
        p.drawArc(QRectF(s / 2 - r, s / 2 - r, 2 * r, 2 * r), 16 * 90, 16 * 270)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(int(s * 0.46), int(s * 0.08), int(s * 0.08), int(s * 0.40), 2, 2)


def main():
    app = QApplication(sys.argv)
    d = Dock()
    d.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()