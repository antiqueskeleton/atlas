from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout


class ExecutiveConsensusPanel(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Executive Consensus")
        title.setObjectName("CardTitle")

        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setMinimumHeight(220)

        layout.addWidget(title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_consensus(self, consensus):
        if not consensus:
            self.body.setPlainText("No executive consensus available.")
            return

        text = consensus.overall_read

        if consensus.areas_of_agreement:
            text += "\n\nAreas of Agreement:\n"
            text += "\n".join(f"• {item}" for item in consensus.areas_of_agreement)

        if consensus.key_risks:
            text += "\n\nKey Risks:\n"
            text += "\n".join(f"• {item}" for item in consensus.key_risks)

        if consensus.recommended_actions:
            text += "\n\nRecommended Actions:\n"
            text += "\n".join(f"• {item}" for item in consensus.recommended_actions)

        self.body.setPlainText(text)