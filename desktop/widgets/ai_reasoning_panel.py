from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class AIReasoningPanel(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("AI Reasoning")
        title.setObjectName("CardTitle")

        self.body = QLabel("No AI reasoning yet.")
        self.body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_reasoning(self, text):
        self.body.setText(text)