import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPixmap, QPainter
from PySide6.QtWidgets import QApplication, QSplashScreen

from desktop.windows.main_window import AtlasMainWindow
from desktop.theme.styles import STYLE
from desktop.theme.colors import NAVY, PRIMARY, ACCENT, SILVER, STEEL


def _make_splash() -> QSplashScreen:
    W, H = 560, 340
    pix = QPixmap(W, H)
    pix.fill(QColor(NAVY))

    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    # "ATLAS" title
    f = QFont("Segoe UI", 54, QFont.Bold)
    f.setLetterSpacing(QFont.AbsoluteSpacing, 10)
    p.setFont(f)
    p.setPen(QColor(PRIMARY))
    p.drawText(0, 60, W, 100, Qt.AlignHCenter | Qt.AlignVCenter, "ATLAS")

    # Tagline
    f2 = QFont("Segoe UI", 10)
    f2.setLetterSpacing(QFont.AbsoluteSpacing, 3)
    p.setFont(f2)
    p.setPen(QColor(ACCENT))
    p.drawText(0, 150, W, 30, Qt.AlignHCenter | Qt.AlignVCenter, "AI INTELLIGENCE PLATFORM")

    # Divider
    p.setPen(QColor(STEEL))
    p.drawLine(W // 2 - 80, 195, W // 2 + 80, 195)

    # Status line
    f3 = QFont("Segoe UI", 9)
    p.setFont(f3)
    p.setPen(QColor(SILVER))
    p.drawText(0, 210, W, 24, Qt.AlignHCenter | Qt.AlignVCenter, "Initializing knowledge engine…")

    # Bottom version
    f4 = QFont("Segoe UI", 8)
    p.setFont(f4)
    p.setPen(QColor(STEEL))
    p.drawText(0, H - 28, W, 20, Qt.AlignHCenter | Qt.AlignVCenter, "Firman Power Equipment  ·  v0.2")

    p.end()
    return QSplashScreen(pix, Qt.WindowStaysOnTopHint)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    splash = _make_splash()
    splash.show()
    app.processEvents()

    window = AtlasMainWindow()

    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
