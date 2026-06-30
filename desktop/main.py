import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from desktop.windows.main_window import AtlasMainWindow
from desktop.theme.styles import STYLE
from desktop.theme.colors import STEEL

_IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"


def _make_splash() -> QSplashScreen:
    pix = QPixmap(str(_IMAGES_DIR / "atlas_splash.png"))
    if pix.isNull():
        # Fallback drawn splash if image missing
        from desktop.theme.colors import NAVY, PRIMARY, ACCENT, SILVER
        W, H = 560, 340
        pix = QPixmap(W, H)
        pix.fill(QColor(NAVY))
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont("Segoe UI", 54, QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 10)
        p.setFont(f)
        p.setPen(QColor(PRIMARY))
        p.drawText(0, 60, W, 100, Qt.AlignHCenter | Qt.AlignVCenter, "ATLAS")
        f2 = QFont("Segoe UI", 10)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        p.setFont(f2)
        p.setPen(QColor(ACCENT))
        p.drawText(0, 150, W, 30, Qt.AlignHCenter | Qt.AlignVCenter, "AI INTELLIGENCE PLATFORM")
        p.end()
    else:
        pix = pix.scaledToWidth(700, Qt.SmoothTransformation)
        p = QPainter(pix)
        f = QFont("Segoe UI", 8)
        p.setFont(f)
        p.setPen(QColor(STEEL))
        p.drawText(
            0, pix.height() - 26, pix.width(), 20,
            Qt.AlignHCenter | Qt.AlignVCenter,
            "dweeb.co  ·  v0.7",
        )
        p.end()

    return QSplashScreen(pix, Qt.WindowStaysOnTopHint)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    icon = QIcon(str(_IMAGES_DIR / "atlas_icon.png"))
    app.setWindowIcon(icon)

    splash = _make_splash()
    splash.show()
    app.processEvents()

    window = AtlasMainWindow()
    window.setWindowIcon(icon)

    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
