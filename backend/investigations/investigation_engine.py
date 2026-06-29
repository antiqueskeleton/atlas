from backend.investigations.question_interpreter import QuestionInterpreter
from backend.investigations.investigation_planner import InvestigationPlanner
from backend.investigations.investigation_executor import InvestigationExecutor
from backend.investigations.executive_summary_generator import ExecutiveSummaryGenerator
from backend.investigations.recommendation_generator import RecommendationGenerator
from backend.investigations.evidence_ranker import EvidenceRanker
from backend.ai.ai_service import AIService
from backend.investigations.agent_result_synthesizer import AgentResultSynthesizer
from backend.investigations.executive_consensus_engine import ExecutiveConsensusEngine


class InvestigationEngine:
    def __init__(self, atlas_app):
        self.app = atlas_app
        self.provider_manager = atlas_app.provider_manager

        self.consensus_engine = ExecutiveConsensusEngine()
        self.interpreter = QuestionInterpreter()
        self.planner = InvestigationPlanner()
        self.executor = InvestigationExecutor(atlas_app.provider_manager)
        self.agent_synthesizer = AgentResultSynthesizer()
        self.summary_generator = ExecutiveSummaryGenerator()
        self.recommendation_generator = RecommendationGenerator()
        self.evidence_ranker = EvidenceRanker()
        self.ai_service = AIService(atlas_app.provider_manager)

    def investigate(self, question: str, progress_callback=None) -> dict:
        def _emit(step, current, total):
            if progress_callback:
                progress_callback(step, current, total)

        _emit("Interpreting question…", 0, 10)
        request = self.interpreter.interpret(question)
        plan = self.planner.build(question)

        _emit("Loading visibility database…", 1, 10)
        analysis = self.app.analyze_from_visibility_db()

        n_tasks = len(plan.tasks)

        def _agent_progress(task, i, total):
            _emit(f"Agent: {task}  ({i}/{total})", 1 + i, 1 + n_tasks + 4)

        task_results = self.executor.execute(
            plan, analysis, request,
            progress_callback=_agent_progress,
        )

        _emit("Synthesizing agent findings…", 2 + n_tasks, 10)
        agent_summary = self.agent_synthesizer.synthesize(task_results)

        _emit("Generating executive consensus…", 3 + n_tasks, 10)
        executive_consensus = self.consensus_engine.generate(
            task_results, self.provider_manager
        )

        _emit("Building summary…", 4 + n_tasks, 10)
        summary = self.summary_generator.generate(request, analysis)
        recommendation = self.recommendation_generator.generate(request, analysis)
        ranked_evidence = self.evidence_ranker.rank(request, analysis)

        _emit("AI reasoning pass…", 5 + n_tasks, 10)
        ai_reasoning = self.ai_service.reason(request, analysis)

        return {
            "request": request,
            "plan": plan,
            "task_results": task_results,
            "analysis": analysis,
            "executive_consensus": executive_consensus,
            "summary": summary,
            "recommendation": recommendation,
            "ranked_evidence": ranked_evidence,
            "ai_reasoning": ai_reasoning,
            "agent_summary": agent_summary,
            "provider": ai_reasoning.provider,
        }
