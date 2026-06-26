from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class IntentPanel(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Question Interpretation")
        title.setObjectName("CardTitle")

        self.body = QLabel("No question interpreted yet.")
        self.body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_request(self, request):
        self.body.setText(
            f"Intent: {request.intent}\n"
            f"Target Brand: {request.target_brand or '-'}\n"
            f"Competitor: {request.competitor or '-'}\n"
            f"Target Feature: {request.target_feature or '-'}"
        )