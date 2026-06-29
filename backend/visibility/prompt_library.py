import csv
from collections import defaultdict
from pathlib import Path


class PromptLibrary:
    PROMPTS_CSV = Path("data/prompts.csv")
    MARKET_QUESTIONS_CSV = Path("data/market_questions.csv")

    def __init__(self):
        self._by_scenario = self._load_by_scenario()
        self._by_family = self._load_by_family()

    # ── Public API ────────────────────────────────────────────────────────────

    def list_sets(self):
        """Return sorted list of available prompt set names."""
        sets = ["default"]
        if self._by_scenario:
            sets += sorted(self._by_scenario.keys())
        if self._by_family:
            sets.append("market questions")
        return sets

    def get(self, prompt_set):
        """Return a list of prompt strings for the given set name."""
        key = prompt_set.lower().strip()

        if key == "default":
            return self._default_prompts()

        if key == "market questions" and self._by_family:
            return self._top_market_questions(limit=10)

        if key in self._by_scenario:
            return self._by_scenario[key]

        return self._default_prompts()

    # ── Loaders ───────────────────────────────────────────────────────────────

    def _load_by_scenario(self):
        if not self.PROMPTS_CSV.exists():
            return {}

        by_scenario = defaultdict(list)
        with self.PROMPTS_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                scenario = row.get("scenario", "").strip().lower()
                text = row.get("prompt_text", "").strip()
                if scenario and text:
                    by_scenario[scenario].append(text)

        return dict(by_scenario)

    def _load_by_family(self):
        if not self.MARKET_QUESTIONS_CSV.exists():
            return {}

        by_family = defaultdict(list)
        with self.MARKET_QUESTIONS_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                family = row.get("family_name", "").strip()
                text = row.get("prompt_text", "").strip()
                score = row.get("prompt_influence_score", "0")
                if family and text:
                    try:
                        by_family[family].append((int(score), text))
                    except ValueError:
                        by_family[family].append((0, text))

        return dict(by_family)

    def _top_market_questions(self, limit=10):
        """Return the highest-scored prompt from each family, sorted by score."""
        top = []
        for prompts in self._by_family.values():
            best = max(prompts, key=lambda x: x[0])
            top.append(best)
        top.sort(key=lambda x: -x[0])
        return [text for _, text in top[:limit]]

    def _default_prompts(self):
        if self._by_scenario:
            # Pull top prompts across all scenarios (first entry per scenario)
            prompts = []
            for texts in self._by_scenario.values():
                if texts:
                    prompts.append(texts[0])
            if prompts:
                return prompts[:10]

        return [
            "What is the best portable generator for home backup?",
            "What is the best portable generator for RV camping?",
            "Which generator brands are most reliable?",
            "What is the best dual fuel portable generator?",
            "Which portable generator is the best value?",
        ]
