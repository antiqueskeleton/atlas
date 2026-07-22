"""
#34: compact always-on-top progress window, shown when the app is minimized
while a Visibility collection is running — kick off a long run, minimize,
and keep an eye on it from any other app without the full window in the way.
Clicking anywhere on it restores Atlas.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class MiniProgressWindow(QWidget):
    def __init__(self):
        # Qt.Tool: no taskbar entry of its own (Atlas's minimized entry is
        # already there); frameless + stay-on-top so it reads as a status
        # chip, not another window to manage.
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint)
        self.setFixedSize(260, 64)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Atlas collection running — click to restore")
        self.setStyleSheet(
            "background: #1E3A5F; border-radius: 8px;")
        self._on_restore = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)
        self._title = QLabel("Atlas — collecting…")
        self._title.setStyleSheet(
            "color: white; font-size: 11px; font-weight: 700; background: transparent;")
        self._bar = QProgressBar()
        self._bar.setFixedHeight(10)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            "QProgressBar { background: #33455F; border: none; border-radius: 5px; }"
            "QProgressBar::chunk { background: #3E7BC2; border-radius: 5px; }")
        self._status = QLabel("")
        self._status.setStyleSheet(
            "color: #C6D2E1; font-size: 10px; background: transparent;")
        lay.addWidget(self._title)
        lay.addWidget(self._bar)
        lay.addWidget(self._status)

    def show_for_run(self, on_restore=None):
        """Place in the bottom-right corner of the primary screen and show.
        on_restore is called when the user clicks the chip."""
        self._on_restore = on_restore
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 16,
                      geo.bottom() - self.height() - 16)
        self.show()
        self.raise_()

    def update_progress(self, done: int, total: int):
        self._bar.setRange(0, max(total, 1))
        self._bar.setValue(done)
        self._status.setText(f"{done}/{total} prompts")

    def set_status(self, text: str):
        self._status.setText(text)

    def mousePressEvent(self, event):
        if self._on_restore:
            self._on_restore()
        self.hide()
        event.accept()
