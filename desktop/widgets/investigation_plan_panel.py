from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout


class InvestigationPlanPanel(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Investigation Plan")
        title.setObjectName("CardTitle")

        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setMinimumHeight(140)

        layout.addWidget(title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_plan(self, plan):
        if not plan:
            self.body.setPlainText("No investigation plan created.")
            return

        text = "\n".join(
            f"• {task}"
            for task in plan.tasks
        )

        self.body.setPlainText(text)