from collections import Counter

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class RelationshipExplorer(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("StatCard")

        layout = QVBoxLayout()

        title = QLabel("Relationship Explorer")
        title.setObjectName("CardTitle")

        self.body = QLabel("No relationships yet.")
        self.body.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(self.body)

        self.setLayout(layout)

    def set_relationships(self, relationships):
        counter = Counter(
            f"{relationship.source} → {relationship.target}"
            for relationship in relationships
        )

        lines = [
            f"{relationship}: {count}"
            for relationship, count in counter.most_common(12)
        ]

        self.body.setText("\n".join(lines) if lines else "No relationships found.")