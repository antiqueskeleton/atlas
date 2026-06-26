from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ResultPanel(QFrame):
    def __init__(self, title):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")

        self.body = QLabel("No results yet.")
        self.body.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_text(self, text):
        self.body.setText(text)