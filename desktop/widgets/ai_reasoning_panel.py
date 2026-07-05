from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout


class AIReasoningPanel(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("AI Reasoning")
        title.setObjectName("CardTitle")

        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setMinimumHeight(260)

        layout.addWidget(title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_reasoning(self, reasoning):
        # #77: an error result (no API key, request failed, or a response
        # that couldn't be parsed) was previously rendered identically to a
        # real, successful analysis — nothing here ever checked is_error, so
        # a technical failure was visually indistinguishable from genuine
        # findings. Style it as a clear warning instead.
        if getattr(reasoning, "is_error", False):
            self.body.setStyleSheet(
                "QTextEdit { background-color: #FEF2F2; border: 1px solid #FCA5A5; "
                "color: #7F1D1D; }"
            )
            text = "⚠ This request did not complete successfully — the text below is NOT a real analysis.\n\n"
            text += reasoning.executive_summary
        else:
            self.body.setStyleSheet("")
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

        if reasoning.raw_response:
            text += "\n\nRaw Response:\n"
            text += reasoning.raw_response

        self.body.setPlainText(text)