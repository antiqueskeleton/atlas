"""
Monochrome thin-stroke nav icons, painted in code (2026-07 redesign).

The rail previously used emoji, which Windows renders in full color via
Segoe UI Emoji — nine clashing multicolor glyphs against the navy rail.
The spec calls for a single technical line-icon family (Lucide-like,
stroke ~1.5). These are minimal QPainter equivalents: silver at rest,
white on the selected row (QIcon.Selected mode).
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_S = 36  # painted at 2x the 18px icon size for crisp downscale


def _painter(pm: QPixmap, color: str) -> QPainter:
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(2.6)          # ~1.3px at display size
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    return p


def _draw(name: str, p: QPainter):
    if name == "home":
        p.drawPolyline([QPointF(7, 17), QPointF(18, 8), QPointF(29, 17)])
        path = QPainterPath(QPointF(10, 15))
        path.lineTo(10, 28); path.lineTo(26, 28); path.lineTo(26, 15)
        p.drawPath(path)
        p.drawRect(QRectF(15.5, 21, 5, 7))
    elif name == "eye":
        path = QPainterPath(QPointF(6, 18))
        path.cubicTo(11, 10, 25, 10, 30, 18)
        path.cubicTo(25, 26, 11, 26, 6, 18)
        p.drawPath(path)
        p.drawEllipse(QPointF(18, 18), 3.6, 3.6)
    elif name == "target":
        p.drawEllipse(QPointF(18, 18), 10, 10)
        p.drawEllipse(QPointF(18, 18), 5.5, 5.5)
        p.drawEllipse(QPointF(18, 18), 1.2, 1.2)
    elif name == "trend":
        p.drawPolyline([QPointF(7, 26), QPointF(14, 18), QPointF(19, 22),
                        QPointF(29, 11)])
        p.drawPolyline([QPointF(23, 11), QPointF(29, 11), QPointF(29, 17)])
    elif name == "bulb":
        path = QPainterPath()
        path.moveTo(13, 22)
        path.cubicTo(9, 18, 10, 10, 18, 9)
        path.cubicTo(26, 10, 27, 18, 23, 22)
        p.drawPath(path)
        p.drawLine(QPointF(14, 25), QPointF(22, 25))
        p.drawLine(QPointF(15.5, 28.5), QPointF(20.5, 28.5))
    elif name == "search":
        p.drawEllipse(QPointF(16, 16), 8, 8)
        p.drawLine(QPointF(22, 22), QPointF(29, 29))
    elif name == "book":
        p.drawRoundedRect(QRectF(8, 8, 20, 20), 2, 2)
        p.drawLine(QPointF(13, 8), QPointF(13, 28))
        p.drawLine(QPointF(17.5, 13), QPointF(24, 13))
        p.drawLine(QPointF(17.5, 17.5), QPointF(24, 17.5))
    elif name == "tag":
        path = QPainterPath(QPointF(8, 9))
        path.lineTo(17, 9); path.lineTo(28, 20); path.lineTo(19, 29)
        path.lineTo(8, 18); path.closeSubpath()
        p.drawPath(path)
        p.drawEllipse(QPointF(13.5, 14.5), 1.4, 1.4)
    elif name == "gear":
        p.drawEllipse(QPointF(18, 18), 4.2, 4.2)
        p.drawEllipse(QPointF(18, 18), 9.5, 9.5)
        for dx, dy in ((0, -13), (0, 13), (-13, 0), (13, 0),
                       (-9.2, -9.2), (9.2, 9.2), (-9.2, 9.2), (9.2, -9.2)):
            p.drawLine(QPointF(18 + dx * 0.73, 18 + dy * 0.73),
                       QPointF(18 + dx, 18 + dy))


def nav_icon(name: str, normal: str = "#A9BBCD", active: str = "#FFFFFF") -> QIcon:
    icon = QIcon()
    for color, mode in ((normal, QIcon.Normal), (active, QIcon.Selected)):
        pm = QPixmap(_S, _S)
        pm.fill(Qt.transparent)
        p = _painter(pm, color)
        _draw(name, p)
        p.end()
        icon.addPixmap(pm, mode)
    return icon
