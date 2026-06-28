from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


class ScrollableCard(QFrame):
    def __init__(self, title):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(170)

        layout.addWidget(title_label)
        layout.addWidget(self.text)

        self.setLayout(layout)

    def set_text(self, text):
        self.text.setPlainText(text)

    def append_text(self, text):
        self.text.append(text)

    def clear(self):
        self.text.clear()