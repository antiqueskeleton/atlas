from backend.investigations.question_interpreter import QuestionInterpreter
from backend.investigations.executive_summary_generator import ExecutiveSummaryGenerator
from backend.investigations.recommendation_generator import RecommendationGenerator
from backend.investigations.evidence_ranker import EvidenceRanker
from backend.ai.ai_service import AIService


class InvestigationEngine:

    def __init__(self, atlas_app):
        self.app = atlas_app

        self.interpreter = QuestionInterpreter()
        self.summary_generator = ExecutiveSummaryGenerator()
        self.recommendation_generator = RecommendationGenerator()
        self.evidence_ranker = EvidenceRanker()

        self.ai_service = AIService(
            atlas_app.provider_manager
        )

    def investigate(self, question: str):

        request = self.interpreter.interpret(question)

        analysis = self.app.analyze_active_dataset()

        summary = self.summary_generator.generate(
            request,
            analysis
        )

        recommendation = self.recommendation_generator.generate(
            request,
            analysis
        )

        ranked_evidence = self.evidence_ranker.rank(
            request,
            analysis
        )

        ai_reasoning = self.ai_service.reason(
            request,
            analysis
        )

        return {
            "request": request,
            "analysis": analysis,
            "summary": summary,
            "recommendation": recommendation,
            "ranked_evidence": ranked_evidence,
            "ai_reasoning": ai_reasoning,
            "provider": ai_reasoning.provider,
        }