from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class InvestigationPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        title = QLabel("Investigate")
        title.setStyleSheet("font-size: 30px; font-weight: bold;")

        subtitle = QLabel("Ask Atlas why a brand, feature, or competitor is winning.")
        subtitle.setStyleSheet("font-size: 15px; color: #6B7280;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()

        self.setLayout(layout)