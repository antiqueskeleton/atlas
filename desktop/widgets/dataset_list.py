from PySide6.QtWidgets import QFrame, QLabel, QListWidget, QVBoxLayout


class DatasetList(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Datasets")
        title.setObjectName("CardTitle")

        self.list = QListWidget()

        layout.addWidget(title)
        layout.addWidget(self.list)

        self.setLayout(layout)

    def set_datasets(self, datasets):
        self.list.clear()

        for dataset in datasets:
            self.list.addItem(f"{dataset.name} ({dataset.response_count})")