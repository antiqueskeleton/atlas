class RecommendationGenerator:
    def generate(self, request, analysis):
        if analysis is None:
            return {
                "text": "Import or analyze a dataset before generating recommendations.",
                "confidence": "Low"
            }

        target = request.target_brand or "the target brand"

        if request.target_feature == "Quiet Operation":
            return {
                "text": f"Strengthen {target}'s messaging around Quiet Operation and inverter performance.",
                "confidence": "Medium"
            }

        if request.intent == "compare":
            competitor = request.competitor or "competitors"
            return {
                "text": f"Compare {target}'s strongest feature associations against {competitor} and create content that closes the biggest gaps.",
                "confidence": "Medium"
            }

        if request.intent == "explain":
            return {
                "text": f"Review where {target} appears less often than competitors and improve messaging around the most repeated feature gaps.",
                "confidence": "Medium"
            }

        return {
            "text": "Review brand-feature relationships and prioritize content around the strongest unmet opportunities.",
            "confidence": "Medium"
        }