import sys

from PySide6.QtWidgets import QApplication

from desktop.windows.main_window import AtlasMainWindow

from desktop.theme.styles import STYLE


def main():

    app = QApplication(sys.argv)

    app.setStyleSheet(STYLE)

    window = AtlasMainWindow()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()