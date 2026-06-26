from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class KnowledgePage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        title = QLabel("Knowledge")
        title.setStyleSheet("font-size: 30px; font-weight: bold;")

        subtitle = QLabel("Manage brands, features, products, personas, and market questions.")
        subtitle.setStyleSheet("font-size: 15px; color: #6B7280;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()

        self.setLayout(layout)