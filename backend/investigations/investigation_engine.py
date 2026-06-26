from backend.investigations.question_interpreter import QuestionInterpreter
from backend.investigations.executive_summary_generator import ExecutiveSummaryGenerator


class InvestigationEngine:

    def __init__(self, atlas_app):
        self.app = atlas_app
        self.interpreter = QuestionInterpreter()
        self.summary_generator = ExecutiveSummaryGenerator()

    def investigate(self, question: str):
        request = self.interpreter.interpret(question)
        analysis = self.app.analyze_active_dataset()

        summary = self.summary_generator.generate(request, analysis)

        return {
            "request": request,
            "analysis": analysis,
            "summary": summary,
        }