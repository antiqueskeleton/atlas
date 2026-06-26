from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QPushButton


class RecommendationCard(QFrame):
    def __init__(self, title="Recommendation", recommendation="No recommendation yet.", confidence=""):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")

        self.recommendation = QLabel(recommendation)
        self.recommendation.setWordWrap(True)
        self.recommendation.setStyleSheet("font-size:15px;font-weight:bold;")

        self.confidence = QLabel(confidence)
        self.confidence.setObjectName("CardSubtitle")

        self.button = QPushButton("Explain")

        layout.addWidget(self.title)
        layout.addWidget(self.recommendation)
        layout.addWidget(self.confidence)
        layout.addWidget(self.button)

        self.setLayout(layout)

    def set_recommendation(self, text, confidence="Confidence: Medium"):
        self.recommendation.setText(text)
        self.confidence.setText(confidence)