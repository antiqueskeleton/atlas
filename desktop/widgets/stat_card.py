from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class StatCard(QFrame):

    def __init__(self, title, value="-", subtitle=""):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")

        self.value = QLabel(value)
        self.value.setObjectName("CardValue")

        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("CardSubtitle")

        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.subtitle)

        self.setLayout(layout)

    def set_value(self, value):
        self.value.setText(str(value))

    def set_subtitle(self, text):
        self.subtitle.setText(text)