import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QWidget,
    QVBoxLayout,
    QStatusBar,
    QTabWidget,
)


class AtlasMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Atlas AI Intelligence Platform")
        self.resize(1100, 700)

        tabs = QTabWidget()
        tabs.addTab(self.build_welcome_tab(), "Executive")
        tabs.addTab(QWidget(), "Investigations")
        tabs.addTab(QWidget(), "Trends")
        tabs.addTab(QWidget(), "Knowledge")
        tabs.addTab(QWidget(), "Settings")

        self.setCentralWidget(tabs)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready.")

    def build_welcome_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()

        title = QLabel("Atlas AI Intelligence Platform")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")

        subtitle = QLabel("Transform market evidence into business intelligence.")
        subtitle.setStyleSheet("font-size: 16px;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()

        widget.setLayout(layout)
        return widget


def main():
    app = QApplication(sys.argv)
    window = AtlasMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()