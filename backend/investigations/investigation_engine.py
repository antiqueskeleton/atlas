from backend.investigations.question_interpreter import QuestionInterpreter
from backend.investigations.executive_summary_generator import ExecutiveSummaryGenerator
from backend.investigations.recommendation_generator import RecommendationGenerator


class InvestigationEngine:

    def __init__(self, atlas_app):
        self.app = atlas_app
        self.interpreter = QuestionInterpreter()
        self.summary_generator = ExecutiveSummaryGenerator()
        self.recommendation_generator = RecommendationGenerator()

    def investigate(self, question: str):
        request = self.interpreter.interpret(question)
        analysis = self.app.analyze_active_dataset()

        summary = self.summary_generator.generate(request, analysis)
        recommendation = self.recommendation_generator.generate(request, analysis)

        return {
            "request": request,
            "analysis": analysis,
            "summary": summary,
            "recommendation": recommendation,
        }