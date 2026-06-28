from backend.agents.competitive_position_agent import CompetitivePositionAgent
from backend.agents.comp_shop_agent import CompShopAgent
from backend.agents.customer_fit_agent import CustomerFitAgent
from backend.agents.feature_comparison_agent import FeatureComparisonAgent


class AgentRegistry:

    @staticmethod
    def build():
        return {
            "Competitive Positioning": CompetitivePositionAgent(),
            "Comp Shop": CompShopAgent(),
            "Customer Fit": CustomerFitAgent(),
            "Feature Comparison": FeatureComparisonAgent(),
        }