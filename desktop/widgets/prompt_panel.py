from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout


class PromptPanel(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Prompt Sent to AI")
        title.setObjectName("CardTitle")

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(220)

        layout.addWidget(title)
        layout.addWidget(self.text)

        self.setLayout(layout)

    def set_prompt(self, prompt):
        self.text.setPlainText(prompt or "No prompt available.")