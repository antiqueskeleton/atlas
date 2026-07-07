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
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

_PRIMARY_STYLE = (
    "QPushButton { font-size: 12px; font-weight: 600; color: white; "
    "background: #0B84FF; border: none; border-radius: 5px; padding: 4px 14px; }"
    "QPushButton:hover { background: #0056CC; }"
    "QPushButton:pressed { background: #003D99; }"
    "QPushButton:disabled { background: #9CA3AF; }"
)

_SECONDARY_STYLE = (
    "QPushButton { font-size: 12px; font-weight: 600; color: #0B84FF; "
    "background: white; border: 1.5px solid #0B84FF; border-radius: 5px; padding: 4px 14px; }"
    "QPushButton:hover { background: #EFF6FF; }"
    "QPushButton:pressed { background: #DBEAFE; }"
    "QPushButton:disabled { color: #9CA3AF; border-color: #9CA3AF; }"
)


def export_button(label: str, tooltip: str = "", primary: bool = False) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(28)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(_PRIMARY_STYLE if primary else _SECONDARY_STYLE)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn
