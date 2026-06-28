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
        self.body.setMinimumHeight(180)

        layout.addWidget(title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_results(self, task_results):
        if not task_results:
            self.body.setPlainText("No investigation tasks completed.")
            return

        text = "\n\n".join(
            f"{result.task}\n"
            f"Confidence: {result.confidence}\n"
            f"{result.summary}"
            for result in task_results
        )

        self.body.setPlainText(text)