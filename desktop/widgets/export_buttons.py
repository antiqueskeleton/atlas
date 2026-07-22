"""
Shared export-button factory (#86) — every page's export controls come from
here so they stay visually identical without each page hand-copying style
strings (which is exactly how Visibility/Intelligence/Price Comparison
drifted to three slightly different heights and paddings).

Convention, applied app-wide:
  - primary (solid blue)   = the page's formatted PDF report — the most
                             complete, shareable artifact the page produces
  - secondary (outline)    = every other export (Excel/Word/scoped exports)
  - placement              = right end of the page's toolbar row, scoped/
                             partial exports left, PDF right-most
"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QPushButton

_PRIMARY_STYLE = (
    "QPushButton { font-size: 12px; font-weight: 600; color: white; "
    "background: #3E7BC2; border: none; border-radius: 5px; padding: 4px 14px; }"
    "QPushButton:hover { background: #295A94; }"
    "QPushButton:pressed { background: #003D99; }"
    "QPushButton:disabled { background: #8C96A2; }"
)

_SECONDARY_STYLE = (
    "QPushButton { font-size: 12px; font-weight: 600; color: #3E7BC2; "
    "background: white; border: 1.5px solid #3E7BC2; border-radius: 5px; padding: 4px 14px; }"
    "QPushButton:hover { background: #EFF6FF; }"
    "QPushButton:pressed { background: #DBEAFE; }"
    "QPushButton:disabled { color: #8C96A2; border-color: #8C96A2; }"
)


def export_button(label: str, tooltip: str = "", primary: bool = False) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(28)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(_PRIMARY_STYLE if primary else _SECONDARY_STYLE)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


# ── Icon-only export buttons ──────────────────────────────────────────────────
# Small colored app icons (Excel green / Word blue / Acrobat red) instead of a
# text button — the recognizable-at-a-glance convention most apps use for
# this, drawn with QPainter rather than bundling actual Microsoft/Adobe
# artwork. Shared across pages so Visibility and Intelligence's export
# buttons look identical rather than each page drawing its own.
_ICON_SPEC = {
    "excel": ("#217346", "XLS"),
    "pdf":   ("#C24536", "PDF"),
    "word":  ("#2B579A", "DOC"),
}


def icon_export_button(kind: str, tooltip: str = "") -> QPushButton:
    color, glyph = _ICON_SPEC[kind]
    size = 30
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(0, 0, size, size, 6, 6)
    p.setPen(QColor("white"))
    p.setFont(QFont("Inter", 8, QFont.Bold))
    p.drawText(pix.rect(), Qt.AlignCenter, glyph)
    p.end()

    btn = QPushButton()
    btn.setIcon(QIcon(pix))
    btn.setIconSize(QSize(size, size))
    btn.setFixedSize(size + 6, size + 6)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        "QPushButton { border: none; background: transparent; border-radius: 6px; }"
        "QPushButton:hover { background: #F3F4F6; }"
        "QPushButton:pressed { background: #E3E7ED; }"
    )
    if tooltip:
        btn.setToolTip(tooltip)
    return btn
