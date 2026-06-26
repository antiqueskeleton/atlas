from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

from backend.models.relationship import Relationship


@dataclass
class RelationshipSummary:
    relationships: List[Relationship]
    top_relationships: Dict[str, int] = field(default_factory=dict)

    def build(self):
        counter = Counter()

        for relationship in self.relationships:
            key = f"{relationship.source} → {relationship.target}"
            counter[key] += 1

        self.top_relationships = dict(counter.most_common(10))
        return self