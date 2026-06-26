from backend.investigations.question_interpreter import QuestionInterpreter
from backend.investigations.executive_summary_generator import ExecutiveSummaryGenerator
from backend.investigations.recommendation_generator import RecommendationGenerator
from backend.investigations.evidence_ranker import EvidenceRanker
from backend.ai.provider_manager import ProviderManager


class InvestigationEngine:

    def __init__(self, atlas_app, provider_manager=None):
        self.app = atlas_app
        self.interpreter = QuestionInterpreter()
        self.summary_generator = ExecutiveSummaryGenerator()
        self.recommendation_generator = RecommendationGenerator()
        self.evidence_ranker = EvidenceRanker()
        self.provider_manager = provider_manager or ProviderManager()

    def investigate(self, question: str):
        request = self.interpreter.interpret(question)
        analysis = self.app.analyze_active_dataset()

        summary = self.summary_generator.generate(request, analysis)
        recommendation = self.recommendation_generator.generate(request, analysis)
        ranked_evidence = self.evidence_ranker.rank(request, analysis)

        provider = self.provider_manager.get_active_provider()

        ai_reasoning = provider.ask(
            prompt=question,
            context=summary
        )

        return {
            "request": request,
            "analysis": analysis,
            "summary": summary,
            "recommendation": recommendation,
            "ranked_evidence": ranked_evidence,
            "ai_reasoning": ai_reasoning,
            "provider": provider.provider_name,
        }