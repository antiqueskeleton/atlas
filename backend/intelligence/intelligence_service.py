import csv
import re
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from backend.intelligence.analysts import BuyingJourneyAnalyst, PersonaAnalyst, ProductAnalyst
from backend.intelligence.intelligence_repository import IntelligenceRepository
from backend.visibility.visibility_repository import VisibilityRepository


_OPPORTUNITY_PROMPT_TEMPLATE = """\
You are a market intelligence analyst for the portable generator industry. \
Your output will drive real marketing decisions, so every opportunity must be grounded in the \
data below — not in general industry knowledge.

RULES:
- EVIDENCE must cite a specific count ("X of Y responses...") or quote a sentence directly from \
the data. Do not write generic observations.
- TACTICS must name specific platforms, programs, or content types — not vague instructions. \
Examples of the required specificity: "Enroll in Amazon Vine and automate Seller Central \
Request-a-Review"; "Publish a 300-word comparison page targeting '[feature] vs [feature]' \
keyword"; "Seed 2-3 YouTube reviewers in the 50K-500K subscriber range with review units"; \
"Post organic answers in r/preppers and r/DIY with product link in bio".
- If an opportunity cannot be supported by the data, skip it.

RESEARCH DATA ({n_prompts} responses):
{findings}

Identify the top 5 strategic opportunities using this exact format:

OPPORTUNITY [N]: [Short title — what specific gap or weakness needs to change]
EVIDENCE: [Exact count or direct quote from the data above]
ACTION: [One concrete first step, specific enough to assign to a person today]
TACTICS: [2-4 execution examples with platform/program/content-type specifics]
"""

_BRIEFING_PROMPT_TEMPLATE = """\
You are a market intelligence analyst producing a briefing for a generator brand's marketing team.

CRITICAL RULES:
- Every claim must cite a number from the quantitative data provided ("appeared in X of Y \
responses", "mentioned by Z% of responses").
- Do not write generic industry commentary. If the data does not support a statement, omit it.
- Include verbatim quotes from the research excerpts — copy exact sentences, do not paraphrase.
- If a section has insufficient data to draw a real conclusion, say "Insufficient data" rather \
than inventing an observation.

TARGET BRAND: {target_brand}

QUANTITATIVE VISIBILITY DATA:
{brand_block}

VERBATIM EXCERPTS MENTIONING {target_brand}:
{quotes_block}

PRODUCT INTELLIGENCE — what AI models say about this generator category:
{product_block}

CONSUMER PERSONAS — who AI models say buys generators:
{persona_block}

BUYING JOURNEY — how AI models describe the path to purchase:
{journey_block}

WEB PRESENCE SIGNALS (scraped from brand homepages):
{web_block}

Produce a structured briefing with the sections below. Lead every section with a specific \
data point before any analysis.

VISIBILITY SNAPSHOT
State {target_brand}'s exact mention rate and rank. Name the top competitors by count and the \
gap in percentage points.

WHAT AI MODELS SAY ABOUT {target_brand}
Quote at least one verbatim sentence from the research excerpts above. Characterize whether \
the tone is a primary recommendation, a comparison mention, or an absence.

KEY CONSUMER SEGMENTS
Name 2-3 specific buyer types that appeared in the research (e.g., "homeowners preparing for \
hurricane season", "RV owners needing <2000W"). State what purchase driver each segment cited.

BUYING JOURNEY INSIGHTS
What sources do AI models direct consumers to consult? Where in the journey does {target_brand} \
appear or disappear?

GAPS AND RISKS
What is {target_brand} not mentioned for that competitors are? Name the competitor, the context, \
and the count difference. Only include gaps visible in the data above.

RECOMMENDED ACTIONS
For each gap named above give one specific tactic. Match the tactic type to the gap:
- Review count gap → Amazon Vine enrollment, Seller Central Request-a-Review automation, \
  influencer seeding with review units
- Feature association gap → dedicated landing page, YouTube tutorial targeting the feature \
  keyword, press release to trade publications
- Channel gap → retailer co-op program, organic community presence (subreddits, forums), \
  SEO content targeting that channel name + product category
"""

# ── Family → bucket classification ────────────────────────────────────────────
# Terms are matched against lowercase family_name substrings.

_BRAND_TERMS = [
    "brand perception", "brand awareness", "brand intelligence", "brand research",
    "brand sentiment", "brand reputation", "brand comparison",
]

_JOURNEY_TERMS = [
    "channel intelligence", "seo", "web presence", "ai knowledge", "knowledge source",
    "brand comparison", "brand reviews", "brands to avoid", "customer service",
    "rental vs", "professionals recommend", "comparison guide",
    "which generator would", "is expensive generator",
]

_PERSONA_TERMS = [
    "generator for ", "first time", "elderly", "medical equipment", "farm",
    "home office", "large family", "rural", "remote cabin", "mobile business",
    "outdoor event", "apartment", "food truck", "construction", "jobsite",
    "emergency preparedness", "help me choose", "what size generator",
    "best camping", "best rv", "best tailgate", "travel trailer", "toy hauler",
    "fifth wheel", "new homeowner", "hurricane", "best storm", "winter storm",
    "wildfire", "summer outage", "power outage", "best emergency",
]

# Minimum responses per bucket to trust DB data over a live run
_MIN_PER_BUCKET = 3


class IntelligenceService:
    def __init__(self, provider_manager, target_brand=""):
        self.provider_manager = provider_manager
        self.target_brand = target_brand
        self.repository = IntelligenceRepository()
        self._analysts = [ProductAnalyst(), PersonaAnalyst(), BuyingJourneyAnalyst()]

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, provider_name=None) -> dict:
        """
        Run the Intelligence Engine.

        Prefers stored visibility responses (2 synthesis API calls only).
        Falls back to live 14-prompt collection when DB data is insufficient.
        """
        vis_repo = VisibilityRepository()
        raw = vis_repo.list_responses()

        if raw:
            collected = self._classify_visibility_responses(raw)
            buckets_ok = all(
                len(collected[k]) >= _MIN_PER_BUCKET
                for k in ("Product Intelligence", "Consumer Personas", "Buying Journey")
            )
            if buckets_ok:
                return self._synthesize_and_save(provider_name, collected, source="db")

        # Not enough DB data — fall back to live 14-prompt collection
        return self._run_live(provider_name)

    # ── Live collection (original behaviour) ─────────────────────────────────

    def _run_live(self, provider_name=None) -> dict:
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
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_opp = ex.submit(self._run_opportunity_pass, provider, collected)
            f_brief = ex.submit(self._run_briefing_pass, provider, collected, brand_stats)
            opportunities = f_opp.result()
            briefing = f_brief.result()
        parsed_opps = self._parse_opportunities(opportunities)
        if parsed_opps:
            self.repository.save_opportunities(run_id, parsed_opps)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()
        n_responses = sum(len(v) for v in collected.values())

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
            "source": "live",
            "responses_used": n_responses,
        }

    # ── DB-backed synthesis ───────────────────────────────────────────────────

    def _synthesize_and_save(
        self,
        provider_name: str | None,
        collected: dict[str, list[tuple[str, str]]],
        source: str,
    ) -> dict:
        """Run the 2 synthesis passes over pre-classified responses and persist."""
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

        # Save the responses we're synthesising from so the UI can show them
        for analyst_name, pairs in collected.items():
            for prompt, response in pairs:
                self.repository.save_result(
                    run_id=run_id,
                    analyst_name=analyst_name,
                    prompt=prompt,
                    response=response,
                    collected_at=started_at.isoformat(),
                )

        brand_stats = self._count_brands(collected)
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_opp = ex.submit(self._run_opportunity_pass, provider, collected)
            f_brief = ex.submit(self._run_briefing_pass, provider, collected, brand_stats)
            opportunities = f_opp.result()
            briefing = f_brief.result()
        parsed_opps = self._parse_opportunities(opportunities)
        if parsed_opps:
            self.repository.save_opportunities(run_id, parsed_opps)

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()
        n_responses = sum(len(v) for v in collected.values())

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
            "source": source,
            "responses_used": n_responses,
        }

    # ── Classification helpers ────────────────────────────────────────────────

    def _classify_family(self, family_name: str) -> str:
        """Return 'product' | 'persona' | 'journey' | 'brand'."""
        f = family_name.lower()
        # Match generic brand terms OR "[target brand] brand" for any configured target
        target_lower = (self.target_brand or "").lower()
        brand_terms = list(_BRAND_TERMS)
        if target_lower:
            brand_terms.append(f"{target_lower} brand")
        if any(t in f for t in brand_terms):
            return "brand"
        if any(t in f for t in _JOURNEY_TERMS):
            return "journey"
        if any(t in f for t in _PERSONA_TERMS):
            return "persona"
        return "product"

    def _load_prompt_family_map(self) -> dict[str, str]:
        """Return {prompt_text: family_name} from market_questions.csv."""
        from backend.services.paths import get_data_dir
        path = get_data_dir() / "market_questions.csv"
        result: dict[str, str] = {}
        if path.exists():
            with path.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    text = row.get("prompt_text", "").strip()
                    family = row.get("family_name", "").strip()
                    if text and family:
                        result[text] = family
        return result

    def _classify_visibility_responses(
        self, raw_responses: list
    ) -> dict[str, list[tuple[str, str]]]:
        """
        Classify visibility_responses rows into 4 intelligence buckets.

        Row format: (id, run_id, provider, model, prompt, response, collected_at, prompt_set)

        Deduplicates by prompt text (keeps most recent, since list_responses
        returns DESC order). Caps each bucket at 25 responses to stay within
        token limits for the synthesis calls.
        """
        prompt_to_family = self._load_prompt_family_map()

        buckets: dict[str, list[tuple[str, str]]] = {
            "Product Intelligence": [],
            "Consumer Personas": [],
            "Buying Journey": [],
            "Brand Intelligence": [],
        }

        bucket_map = {
            "product": "Product Intelligence",
            "persona": "Consumer Personas",
            "journey": "Buying Journey",
            "brand":   "Brand Intelligence",
        }

        seen: set[str] = set()

        for row in raw_responses:
            prompt     = row[4]
            response   = row[5]
            prompt_set = row[7] if len(row) > 7 else ""

            if prompt in seen:
                continue
            seen.add(prompt)

            # Resolve family: use prompt_set when it's a specific family name,
            # otherwise look up the prompt text in the CSV.
            if prompt_set and prompt_set != "All Prompts":
                family = prompt_set
            else:
                family = prompt_to_family.get(prompt, "")

            bucket_key = self._classify_family(family)
            buckets[bucket_map[bucket_key]].append((prompt, response))

        # Cap each bucket to keep synthesis token cost predictable
        for key in buckets:
            buckets[key] = buckets[key][:25]

        return buckets

    # ── Synthesis passes ──────────────────────────────────────────────────────

    def _run_opportunity_pass(self, provider, collected: dict) -> str:
        all_pairs: list[tuple[str, str]] = []
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
            # Include full responses but cap at 600 chars each to stay within token budget
            return "\n\n".join(f"Q: {p}\nA: {r[:600]}" for p, r in pairs) or "No data."

        target = self.target_brand or "N/A"
        counts = brand_stats.get("counts", {})
        total  = max(brand_stats.get("total_responses", 1), 1)

        # Ranked brand mention table with gap vs target
        target_count = counts.get(target, 0)
        target_rate  = round(target_count / total * 100) if total else 0
        sorted_brands = sorted(counts.items(), key=lambda x: -x[1])
        rank = next((i + 1 for i, (b, _) in enumerate(sorted_brands) if b == target), None)

        brand_lines = "\n".join(
            f"  {'→ ' if b == target else '  '}{b}: {c} of {total} responses "
            f"({round(c / total * 100)}%)"
            for b, c in sorted_brands[:10]
        ) or "  No brand data."

        brand_block = (
            f"{target}: {target_count} of {total} responses ({target_rate}%)"
            + (f", rank #{rank} of {len(sorted_brands)}" if rank else "")
            + f"\n\nAll tracked brands:\n{brand_lines}"
        )

        # Enrich with direct brand perception responses
        brand_direct = collected.get("Brand Intelligence", [])
        if brand_direct:
            brand_block += f"\n\nDIRECT {target.upper()} BRAND PERCEPTION RESPONSES:\n"
            brand_block += "\n\n".join(f"Q: {p}\nA: {r[:500]}" for p, r in brand_direct[:4])

        # Extract verbatim sentences mentioning the target brand
        quotes_block = self._extract_brand_quotes(collected, target, max_quotes=5)

        all_count = sum(len(v) for v in collected.values())
        prompt = _BRIEFING_PROMPT_TEMPLATE.format(
            target_brand=target,
            brand_block=brand_block,
            quotes_block=quotes_block,
            product_block=block("Product Intelligence"),
            persona_block=block("Consumer Personas"),
            journey_block=block("Buying Journey"),
            web_block=self._build_web_block(),
        )
        result = provider.ask(prompt)
        return result.executive_summary or ""

    def _extract_brand_quotes(self, collected: dict, target: str,
                              max_quotes: int = 5) -> str:
        """
        Pull verbatim sentences from stored responses that mention the target brand.
        Prefers sentences where the brand is compared, contrasted, or evaluated.
        """
        if not target or target == "N/A":
            return "No target brand set."

        target_lower = target.lower()
        comparison_signals = ("unlike", "compared", "versus", "vs", "better than",
                              "worse than", "instead of", "over", "recommend",
                              "prefer", "top pick", "best", "not as")

        scored: list[tuple[int, str]] = []

        for pairs in collected.values():
            for _, response in pairs:
                for sentence in re.split(r'(?<=[.!?])\s+', response):
                    if target_lower not in sentence.lower():
                        continue
                    s = sentence.strip()
                    if len(s) < 30 or len(s) > 400:
                        continue
                    # Score higher if it contains a comparison signal
                    score = 2 if any(sig in s.lower() for sig in comparison_signals) else 1
                    scored.append((score, s))

        if not scored:
            return f"No responses directly mentioned {target}."

        # Deduplicate and sort by score, take top N
        seen: set[str] = set()
        unique: list[tuple[int, str]] = []
        for score, s in sorted(scored, key=lambda x: -x[0]):
            if s not in seen:
                seen.add(s)
                unique.append((score, s))

        lines = [f'  "{s}"' for _, s in unique[:max_quotes]]
        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_web_block(self) -> str:
        """Build a web presence summary from scraped web_intelligence rows."""
        try:
            from backend.knowledge.knowledge_repository import KnowledgeRepository
            rows = KnowledgeRepository().list_web_intelligence_for_briefing()
        except Exception:
            return "No web presence data available."
        if not rows:
            return "No web presence data available."
        lines = []
        for brand, domain, title, meta, h1s_json, keywords, da, visits, schema, sitemap, https, scraped in rows:
            if not scraped:
                continue  # skip unscraped manual entries — they have no on-page data
            import json
            try:
                h1s = json.loads(h1s_json or "[]")
            except Exception:
                h1s = []
            h1_str = " | ".join(h1s[:3]) if h1s else "—"
            kw_str = (keywords or "")[:100] or "—"
            signals = []
            if https:
                signals.append("HTTPS")
            if sitemap:
                signals.append("Sitemap")
            if schema:
                signals.append("Schema.org")
            lines.append(
                f"  {brand} ({domain})\n"
                f"    Title: {title or '—'}\n"
                f"    Meta: {meta[:120] if meta else '—'}\n"
                f"    H1(s): {h1_str}\n"
                f"    Top keywords: {kw_str}\n"
                f"    Signals: {', '.join(signals) or 'none'}"
            )
        return "\n\n".join(lines) if lines else "No scraped web data yet — run Scrape All on Knowledge → Web Intelligence tab."

    def _count_brands(self, collected: dict) -> dict:
        brand_terms = self._load_brands()
        counts: Counter = Counter()
        total = 0
        for pairs in collected.values():
            for _, text in pairs:
                total += 1
                lower = text.lower()
                for brand, terms in brand_terms.items():
                    if any(t in lower for t in terms):
                        counts[brand] += 1
        return {"counts": dict(counts), "total_responses": total}

    def _load_brands(self) -> dict[str, list[str]]:
        from backend.knowledge.knowledge_repository import KnowledgeRepository
        terms = KnowledgeRepository().get_brand_detection_terms()
        if not terms:
            defaults = ["Firman", "Westinghouse", "Honda", "Generac", "Yamaha", "Predator", "DuroMax"]
            return {b: [b.lower()] for b in defaults}
        return terms

    @staticmethod
    def _parse_opportunities(text: str) -> list[dict]:
        """Parse LLM opportunity text into structured dicts (title, evidence, description)."""
        pattern = re.compile(
            r"OPPORTUNITY\s*\[?\d+\]?:\s*(.+?)\n"
            r"EVIDENCE:\s*(.*?)\n"
            r"ACTION:\s*(.*?)\n"
            r"(?:TACTICS:\s*(.*?))?(?=\nOPPORTUNITY|\Z)",
            re.DOTALL | re.IGNORECASE,
        )
        results = []
        for m in pattern.finditer(text):
            title = m.group(1).strip()
            if not title:
                continue
            action  = m.group(3).strip()
            tactics = (m.group(4) or "").strip()
            # Combine action + tactics into description so the UI surfaces both
            description = action
            if tactics:
                description += f"\n\nTactics:\n{tactics}"
            results.append({
                "title":       title,
                "evidence":    m.group(2).strip(),
                "description": description,
            })
        return results

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
        return {"run": run, "briefing": briefing, "results": results}

    def total_response_count(self) -> int:
        """Total rows in visibility_responses — the full data reservoir."""
        return VisibilityRepository().count_responses()

    def db_response_counts(self) -> dict[str, int]:
        """Return per-bucket counts from the visibility DB (for UI display)."""
        vis_repo = VisibilityRepository()
        raw = vis_repo.list_responses()
        if not raw:
            return {"Product Intelligence": 0, "Consumer Personas": 0,
                    "Buying Journey": 0, "Brand Intelligence": 0, "total": 0}
        classified = self._classify_visibility_responses(raw)
        result = {k: len(v) for k, v in classified.items()}
        result["total"] = sum(result.values())
        return result
