from backend.models.relationship import Relationship


class RelationshipEngine:

    def generate(self, analysis_results):

        relationships = []

        grouped = {}

        for result in analysis_results:

            grouped.setdefault(result.evidence_id, []).extend(result.findings)

        for evidence_id, findings in grouped.items():

            brands = [
                f for f in findings
                if f.finding_type == "brand"
            ]

            features = [
                f for f in findings
                if f.finding_type == "feature"
            ]

            for brand in brands:

                for feature in features:

                    relationships.append(

                        Relationship(
                            source=brand.value,
                            target=feature.value,
                            relationship_type="brand_feature",
                            evidence_id=evidence_id,
                            confidence=min(
                                brand.confidence,
                                feature.confidence
                            )
                        )

                    )

        return relationships