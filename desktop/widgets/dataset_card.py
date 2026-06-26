from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class DatasetCard(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Current Dataset")
        title.setObjectName("CardTitle")

        self.name = QLabel("No dataset loaded")
        self.name.setStyleSheet(
            "font-size:18px;font-weight:bold;"
        )

        self.details = QLabel("")
        self.details.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.name)
        layout.addWidget(self.details)

        self.setLayout(layout)

    def set_dataset(self, dataset):

        self.name.setText(dataset.name)

        self.details.setText(
            f"""
Source: {dataset.source}

Responses: {dataset.response_count}

Status: {dataset.status}
            """.strip()
        )