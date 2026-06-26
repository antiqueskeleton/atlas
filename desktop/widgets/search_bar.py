from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class SearchBar(QWidget):
    def __init__(self, placeholder="Ask Atlas anything...", button_text="Investigate"):
        super().__init__()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)

        self.button = QPushButton(button_text)

        layout.addWidget(self.input)
        layout.addWidget(self.button)

        self.setLayout(layout)

    def text(self):
        return self.input.text()

    def connect(self, callback):
        self.button.clicked.connect(callback)