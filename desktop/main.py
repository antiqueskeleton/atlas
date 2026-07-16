import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from desktop.theme.styles import STYLE
from desktop.theme.colors import STEEL
from desktop.updater import APP_VERSION

# AtlasMainWindow is deliberately NOT imported here — its import cascade
# (backend services, the openai SDK, page modules) is the single biggest
# chunk of cold-start time, and importing it at module level meant the
# user stared at NOTHING for the whole wait (~20s cold, per real v1.0
# testing). It's imported inside main(), after the splash is on screen,
# so the wait happens behind the splash instead of before it.


def _images_dir() -> Path:
    """
    Frozen-aware images directory (#37). Previously always used
    Path(__file__).resolve().parent.parent — relative-path resolution off
    __file__ is not reliably correct for PyInstaller-frozen modules (the
    file doesn't physically exist at that path; __file__ is a synthesized
    compatibility value), unlike backend/services/paths.py's get_data_dir(),
    which already correctly branches on sys.frozen. This makes main.py match
    that same, proven-correct pattern instead of relying on __file__ behavior
    that varies by PyInstaller version.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "images"
    return Path(__file__).resolve().parent.parent / "images"


_IMAGES_DIR = _images_dir()


def _fonts_dir() -> Path:
    """Frozen-aware, same pattern as _images_dir() (#37)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "fonts"
    return Path(__file__).resolve().parent / "assets" / "fonts"


def _register_inter_font() -> bool:
    """Bundled Inter (SIL OFL) replaces the Segoe UI system default — built
    for small-size UI text (taller x-height, tighter apertures) rather than
    Segoe's general-purpose print/body-text design, which is the better fit
    for Atlas's dense KPI tables and small labels. Static weights only
    (Regular/Medium/SemiBold/Bold), not the variable font: Qt's weight
    selection for static families is far more reliably supported across
    Qt/FreeType versions than variable-font axis selection. Registration
    failure (missing file, bad font data) degrades silently to the
    Segoe UI/Arial fallback already in styles.py's font-family list —
    never a startup error over a cosmetic font swap.

    Returns True if at least one weight registered, so the caller can set
    Inter as the app-wide default font (see _apply_inter_default)."""
    fonts_dir = _fonts_dir()
    loaded = False
    for name in ("Inter-Regular.ttf", "Inter-Medium.ttf",
                 "Inter-SemiBold.ttf", "Inter-Bold.ttf"):
        if QFontDatabase.addApplicationFont(str(fonts_dir / name)) != -1:
            loaded = True
    return loaded


def _apply_inter_default(app):
    """Make Inter the application's ACTUAL default font, not just a
    stylesheet font-family. The `QWidget { font-family: Inter }` rule in
    styles.py cascades to plain widgets, but on Windows it does NOT
    reliably reach item-view text (QTableWidget cells), combo-box popups,
    and native-styled controls — those keep QApplication.font(), which was
    still Segoe UI, so the app looked like two different fonts (user
    report: title Inter, tables/checkboxes not). Setting the app default
    closes that gap for every widget and delegate, regardless of QSS quirks.
    The current default point size is preserved — only the family changes —
    so nothing resizes."""
    if not _register_inter_font():
        return
    font = app.font()
    font.setFamily("Inter")
    app.setFont(font)


def _make_splash() -> QSplashScreen:
    pix = QPixmap(str(_IMAGES_DIR / "atlas_splash.png"))
    if pix.isNull():
        # Fallback drawn splash if image missing
        from desktop.theme.colors import NAVY, PRIMARY, ACCENT
        W, H = 560, 340
        pix = QPixmap(W, H)
        pix.fill(QColor(NAVY))
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont("Inter", 54, QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 10)
        p.setFont(f)
        p.setPen(QColor(PRIMARY))
        p.drawText(0, 60, W, 100, Qt.AlignHCenter | Qt.AlignVCenter, "ATLAS")
        f2 = QFont("Inter", 10)
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        p.setFont(f2)
        p.setPen(QColor(ACCENT))
        p.drawText(0, 150, W, 30, Qt.AlignHCenter | Qt.AlignVCenter, "AI INTELLIGENCE PLATFORM")
        p.end()
    else:
        pix = pix.scaledToWidth(700, Qt.SmoothTransformation)
        p = QPainter(pix)
        f = QFont("Inter", 8)
        p.setFont(f)
        p.setPen(QColor(STEEL))
        p.drawText(
            0, pix.height() - 26, pix.width(), 20,
            Qt.AlignHCenter | Qt.AlignVCenter,
            f"dweeb.co  ·  v{APP_VERSION}",
        )
        p.end()

    return QSplashScreen(pix, Qt.WindowStaysOnTopHint)


def main():
    app = QApplication(sys.argv)
    _apply_inter_default(app)   # registers Inter AND sets it as the default font

    icon = QIcon(str(_IMAGES_DIR / "atlas_icon.png"))
    app.setWindowIcon(icon)

    # Splash is created and shown BEFORE the global stylesheet is applied
    # (#37) — QSplashScreen does its own custom pixmap painting, and applying
    # an app-wide QWidget stylesheet switches Qt's rendering path for every
    # QWidget subclass including QSplashScreen, which can interfere with that
    # custom paintEvent. Showing it first, untouched by STYLE, removes that
    # as a possible cause regardless of whether it was the actual culprit.
    splash = _make_splash()
    splash.show()
    app.processEvents()

    app.setStyleSheet(STYLE)

    # Heavy import happens HERE, behind the visible splash (see the module-
    # level comment) — processEvents first so the splash actually paints.
    app.processEvents()
    from desktop.windows.main_window import AtlasMainWindow

    window = AtlasMainWindow()
    window.setWindowIcon(icon)

    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
