from backend.agents.competitive_position_agent import CompetitivePositionAgent


class AgentRegistry:

    @staticmethod
    def build():
        return {
            "Competitive Positioning": CompetitivePositionAgent(),
        }