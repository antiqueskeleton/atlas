from backend.agents.competitive_position_agent import CompetitivePositionAgent
from backend.agents.comp_shop_agent import CompShopAgent


class AgentRegistry:

    @staticmethod
    def build():
        return {
            "Competitive Positioning": CompetitivePositionAgent(),
            "Comp Shop": CompShopAgent(),
        }