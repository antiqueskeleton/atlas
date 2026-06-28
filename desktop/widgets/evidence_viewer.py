from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


class EvidenceViewer(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Evidence Explorer")
        title.setObjectName("CardTitle")

        self.prompt = QLabel("No evidence selected.")
        self.prompt.setWordWrap(True)

        self.source = QLabel("")
        self.source.setWordWrap(True)

        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setMinimumHeight(220)

        layout.addWidget(title)
        layout.addWidget(self.prompt)
        layout.addWidget(self.source)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_evidence(self, evidence):
        self.prompt.setText(f"<b>Prompt:</b> {evidence.prompt}")
        self.source.setText(f"<b>Source:</b> {evidence.source}")
        self.body.setPlainText(evidence.text)

    def clear(self):
        self.prompt.setText("No evidence selected.")
        self.source.clear()
        self.body.clear()