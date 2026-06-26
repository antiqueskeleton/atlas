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

    def set_reasoning(self, reasoning):
        text = reasoning.executive_summary

        if reasoning.opportunities:
            text += "\n\nOpportunities:\n"
            text += "\n".join(f"• {item}" for item in reasoning.opportunities)

        if reasoning.risks:
            text += "\n\nRisks:\n"
            text += "\n".join(f"• {item}" for item in reasoning.risks)

        if reasoning.follow_up_questions:
            text += "\n\nSuggested Follow-Up Questions:\n"
            text += "\n".join(f"• {item}" for item in reasoning.follow_up_questions)

        text += f"\n\nProvider: {reasoning.provider}"
        text += f"\nConfidence: {reasoning.confidence}"

        self.body.setText(text)