import uuid
from collections import Counter
from datetime import datetime

from backend.intelligence.analysts import BuyingJourneyAnalyst, PersonaAnalyst, ProductAnalyst
from backend.intelligence.intelligence_repository import IntelligenceRepository


_OPPORTUNITY_PROMPT_TEMPLATE = """\
You are a market intelligence analyst for the portable generator industry.

Below are raw AI responses collected from {n_prompts} market research questions covering product \
features, consumer personas, and the buying journey. Analyze these responses and identify the top \
5 strategic opportunities to improve a brand's visibility and positioning in AI-generated content.

For each opportunity, state:
OPPORTUNITY [N]: [Short title]
EVIDENCE: [What the research shows — specific patterns or gaps]
ACTION: [Concrete step to address this opportunity]

Focus on: content gaps, underserved buyer segments, missing brand associations, messaging \
weaknesses, and channels where AI models draw from (Reddit, YouTube, review sites, etc.).

RESEARCH FINDINGS:
{findings}
"""

_BRIEFING_PROMPT_TEMPLATE = """\
You are a senior market intelligence analyst. Write an executive briefing based on AI research \
collected across {n_prompts} questions about the portable generator market.

TARGET BRAND: {target_brand}

PRODUCT INTELLIGENCE (how AI describes the category):
{product_block}

CONSUMER PERSONAS (who AI says buys generators):
{persona_block}

BUYING JOURNEY (how AI describes the purchase process):
{journey_block}

BRAND VISIBILITY FROM RESEARCH:
{brand_block}

Write a structured executive briefing (350-450 words) with these sections:
MARKET LANDSCAPE: [2-3 sentences on the category as AI presents it]
KEY CONSUMER SEGMENTS: [3 specific buyer profiles with motivations]
BUYING JOURNEY INSIGHTS: [How AI describes the path to purchase]
{target_brand} POSITIONING: [Where and how {target_brand} appears — or doesn't — in the research]
STRATEGIC RECOMMENDATIONS:
1. [Specific, actionable recommendation]
2. [Specific, actionable recommendation]
3. [Specific, actionable recommendation]
"""


class IntelligenceService:
    def __init__(self, provider_manager, target_brand=""):
        self.provider_manager = provider_manager
        self.target_brand = target_brand
        self.repository = IntelligenceRepository()
        self._analysts = [ProductAnalyst(), PersonaAnalyst(), BuyingJourneyAnalyst()]

    def run(self, provider_name=None):
        if provider_name and provider_name != self.provider_manager.active_provider_name:
            self.provider_manager.set_active_provider(provider_name)

        provider = self.provider_manager.get_active_provider()

        run_id = str(uuid.uuid4())
        started_at = datetime.now()

        self.repository.save_run(
            run_id=run_id,
            provider=provider.provider_name,
            model=getattr(provider, "model", "unknown"),
            target_brand=self.target_brand,
            started_at=started_at.isoformat(),
        )

        collected: dict[str, list[tuple[str, str]]] = {}

        for analyst in self._analysts:
            collected[analyst.name] = []
            for prompt in analyst.prompts:
                response = provider.ask(prompt)
                text = response.executive_summary or ""
                collected[analyst.name].append((prompt, text))
                self.repository.save_result(
                    run_id=run_id,
                    analyst_name=analyst.name,
                    prompt=prompt,
                    response=text,
                    collected_at=datetime.now().isoformat(),
                )

        brand_stats = self._count_brands(collected)

        opportunities = self._run_opportunity_pass(provider, collected)
        briefing = self._run_briefing_pass(provider, collected, brand_stats)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        self.repository.save_briefing(
            run_id=run_id,
            product_summary=self._join_responses(collected.get("Product Intelligence", [])),
            persona_summary=self._join_responses(collected.get("Consumer Personas", [])),
            journey_summary=self._join_responses(collected.get("Buying Journey", [])),
            opportunities=opportunities,
            executive_briefing=briefing,
            created_at=completed_at.isoformat(),
        )
        self.repository.complete_run(
            run_id=run_id,
            completed_at=completed_at.isoformat(),
            duration_seconds=duration,
        )

        return {
            "run_id": run_id,
            "provider": provider.provider_name,
            "duration_seconds": duration,
            "collected": collected,
            "brand_stats": brand_stats,
            "opportunities": opportunities,
            "executive_briefing": briefing,
        }

    # ── Second-pass synthesis ─────────────────────────────────────────────────

    def _run_opportunity_pass(self, provider, collected: dict) -> str:
        all_pairs = []
        for responses in collected.values():
            all_pairs.extend(responses)

        findings = "\n\n".join(
            f"Q: {p}\nA: {r[:500]}" for p, r in all_pairs
        )
        prompt = _OPPORTUNITY_PROMPT_TEMPLATE.format(
            n_prompts=len(all_pairs),
            findings=findings,
        )
        result = provider.ask(prompt)
        return result.executive_summary or ""

    def _run_briefing_pass(self, provider, collected: dict, brand_stats: dict) -> str:
        def block(name):
            pairs = collected.get(name, [])
            return "\n".join(f"- {r[:400]}" for _, r in pairs) or "No data."

        target = self.target_brand or "N/A"
        counts = brand_stats.get("counts", {})
        total = brand_stats.get("total_responses", 1)
        brand_lines = "\n".join(
            f"- {b}: {c} mention(s) ({round(c/total*100)}%)"
            for b, c in sorted(counts.items(), key=lambda x: -x[1])[:8]
        ) or "No brand data."

        target_count = counts.get(target, 0)
        target_rate = round(target_count / total * 100) if total else 0
        brand_block = (
            f"Brands appearing in responses:\n{brand_lines}\n"
            f"\n{target} appeared in {target_count} of {total} responses ({target_rate}%)."
        )

        all_count = sum(len(v) for v in collected.values())
        prompt = _BRIEFING_PROMPT_TEMPLATE.format(
            n_prompts=all_count,
            target_brand=target,
            product_block=block("Product Intelligence"),
            persona_block=block("Consumer Personas"),
            journey_block=block("Buying Journey"),
            brand_block=brand_block,
        )
        result = provider.ask(prompt)
        return result.executive_summary or ""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _count_brands(self, collected: dict) -> dict:
        brand_list = self._load_brands()
        counts: Counter = Counter()
        total = 0

        for pairs in collected.values():
            for _, text in pairs:
                total += 1
                lower = text.lower()
                for brand in brand_list:
                    if brand.lower() in lower:
                        counts[brand] += 1

        return {"counts": dict(counts), "total_responses": total}

    def _load_brands(self) -> list[str]:
        from pathlib import Path
        path = Path("data/brands.csv")
        if not path.exists():
            return [
                "Firman", "Champion", "Westinghouse",
                "Honda", "Generac", "Yamaha", "Predator",
            ]
        brands = []
        for line in path.read_text(encoding="utf-8").splitlines():
            val = line.strip()
            if not val:
                continue
            if "," in val:
                val = val.split(",")[0].strip()
            if val.lower() not in ("brand", "brands", "name"):
                brands.append(val)
        return brands or ["Firman", "Champion", "Westinghouse", "Honda", "Generac"]

    @staticmethod
    def _join_responses(pairs: list[tuple[str, str]]) -> str:
        return "\n\n".join(f"Q: {p}\nA: {r}" for p, r in pairs)

    # ── Read helpers for UI ───────────────────────────────────────────────────

    def list_runs(self):
        return self.repository.list_runs()

    def get_latest_briefing(self):
        run = self.repository.get_latest_run()
        if not run:
            return None
        run_id = run[0]
        briefing = self.repository.get_briefing_for_run(run_id)
        results = self.repository.get_results_for_run(run_id)
        return {
            "run": run,
            "briefing": briefing,
            "results": results,
        }
