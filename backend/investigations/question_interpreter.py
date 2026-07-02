from backend.models.investigation_request import InvestigationRequest
from backend.models.comp_shop_request import CompShopRequest


class QuestionInterpreter:
    def interpret(self, question: str) -> InvestigationRequest:
        normalized = question.lower()

        request = InvestigationRequest(question=question)

        if any(word in normalized for word in ["why", "lose", "losing", "win", "winning"]):
            request.intent = "explain"

        if any(word in normalized for word in ["compare", "vs", "versus", "against"]):
            request.intent = "compare"

        brands = ["Firman", "Honda", "Westinghouse", "Generac", "Predator", "DuroMax", "Yamaha", "CAT"]

        mentioned_brands = [
            brand for brand in brands
            if brand.lower() in normalized
        ]

        if mentioned_brands:
            request.target_brand = mentioned_brands[0]

        if len(mentioned_brands) > 1:
            request.competitor = mentioned_brands[1]

        feature_map = {
            "quiet": "Quiet Operation",
            "noise": "Quiet Operation",
            "dual fuel": "Dual Fuel",
            "tri fuel": "Tri Fuel",
            "rv": "RV Ready",
            "camping": "RV Ready",
            "electric start": "Electric Start",
            "home backup": "Home Backup",
            "whole home": "Home Backup",
        }

        for keyword, feature in feature_map.items():
            if keyword in normalized:
                request.target_feature = feature
                break

        if any(term in normalized for term in [
            "comp shop",
            "compare product",
            "compare products",
            "product a",
            "against competitor",
            "vs",
            "versus",
        ]):
            request.intent = "comp_shop"
            request.comp_shop = CompShopRequest(
                target_product=request.target_brand or request.target_brand or "Target product",
                competitor_products=[
                    request.competitor
                ] if request.competitor else [],
                category=request.target_feature,
            )

        return request