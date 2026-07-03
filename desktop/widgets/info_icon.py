from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


def info_icon(tooltip_text: str) -> QLabel:
    """
    A small circular info icon (ⓘ) that shows tooltip_text on hover.

    Attach next to any tile/column header where the meaning or calculation
    of a number isn't self-evident to a first-time user — especially where
    two similar-looking metrics are intentionally different (e.g. a rate
    computed against total responses vs. against that brand's own mentions).
    Distinct from control tooltips (setToolTip on buttons/inputs): this is
    specifically for explaining DATA, not interactions.
    """
    icon = QLabel("ⓘ")
    icon.setFixedWidth(14)
    icon.setStyleSheet(
        "QLabel { color: #9CA3AF; font-size: 12px; font-weight: bold; background: transparent; }"
        "QLabel:hover { color: #0B84FF; }"
    )
    icon.setCursor(Qt.PointingHandCursor)
    icon.setToolTip(tooltip_text)
    return icon
