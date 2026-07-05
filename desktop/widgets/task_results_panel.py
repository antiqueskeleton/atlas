from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout


class TaskResultsPanel(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Investigation Tasks")
        title.setObjectName("CardTitle")

        self.body = QTextEdit()
        self.body.setReadOnly(True)

        layout.addWidget(title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_results(self, task_results):
        if not task_results:
            self.body.setPlainText("No investigation tasks completed.")
            return

        # #77: mark a failed/unparsed agent result clearly — previously
        # rendered identically to a real finding, with nothing distinguishing
        # "the AI's response could not be parsed" from actual analysis.
        text = "\n\n".join(
            f"{result.task}"
            + ("  ⚠ FAILED — not a real analysis" if getattr(result, "is_error", False) else "")
            + f"\nConfidence: {result.confidence}\n"
            f"Provider: {result.provider or 'Atlas'}\n"
            f"{result.summary}"
            for result in task_results
        )

        self.body.setPlainText(text)