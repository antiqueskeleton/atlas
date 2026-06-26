from PySide6.QtWidgets import QFrame, QLabel, QListWidget, QVBoxLayout


class DatasetList(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")
        self.datasets = []

        layout = QVBoxLayout()

        title = QLabel("Datasets")
        title.setObjectName("CardTitle")

        self.list = QListWidget()

        layout.addWidget(title)
        layout.addWidget(self.list)

        self.setLayout(layout)

    def set_datasets(self, datasets):
        self.datasets = datasets
        self.list.clear()

        for dataset in datasets:
            self.list.addItem(f"{dataset.name} ({dataset.response_count})")

    def connect_selection_changed(self, callback):
        self.list.currentRowChanged.connect(
            lambda index: callback(self.datasets[index]) if index >= 0 else None
        )