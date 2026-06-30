import csv
from collections import defaultdict
from pathlib import Path

from backend.services.paths import get_data_dir

_ALL_KEY = "All Prompts"


class PromptLibrary:
    @property
    def PROMPTS_CSV(self):
        return get_data_dir() / "prompts.csv"

    @property
    def MARKET_QUESTIONS_CSV(self):
        return get_data_dir() / "market_questions.csv"

    def __init__(self):
        self._by_scenario = self._load_by_scenario()
        self._by_family = self._load_by_family()

    # ── Public API ────────────────────────────────────────────────────────────

    def list_sets(self) -> list[str]:
        """Return ordered list of selectable prompt set names."""
        sets = [_ALL_KEY]
        if self._by_family:
            sets += sorted(self._by_family.keys())
        if self._by_scenario:
            sets += sorted(self._by_scenario.keys())
        return sets

    def list_families(self) -> list[str]:
        return sorted(self._by_family.keys())

    def list_families_by_influence(self) -> list[str]:
        """Return family names sorted by max prompt influence score, descending."""
        scored = [
            (max((s for s, _ in prompts), default=0), name)
            for name, prompts in self._by_family.items()
            if prompts
        ]
        scored.sort(reverse=True)
        return [name for _, name in scored]

    def get(self, prompt_set: str) -> list[str]:
        """Return prompt strings for the given set name."""
        if prompt_set == _ALL_KEY:
            return self._all_prompts()

        if prompt_set in self._by_family:
            return [text for _, text in sorted(self._by_family[prompt_set], key=lambda x: -x[0])]

        key = prompt_set.lower().strip()
        if key in self._by_scenario:
            return self._by_scenario[key]

        return self._default_prompts()

    def count(self, prompt_set: str) -> int:
        """Return prompt count for a set without loading all text."""
        if prompt_set == _ALL_KEY:
            return sum(len(v) for v in self._by_family.values())
        if prompt_set in self._by_family:
            return len(self._by_family[prompt_set])
        key = prompt_set.lower().strip()
        if key in self._by_scenario:
            return len(self._by_scenario[key])
        return len(self._default_prompts())

    # ── Loaders ───────────────────────────────────────────────────────────────

    def _load_by_scenario(self):
        if not self.PROMPTS_CSV.exists():
            return {}
        by_scenario: dict[str, list] = defaultdict(list)
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
        by_family: dict[str, list] = defaultdict(list)
        with self.MARKET_QUESTIONS_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                family = row.get("family_name", "").strip()
                text = row.get("prompt_text", "").strip()
                raw_score = row.get("prompt_influence_score", "0")
                if family and text:
                    try:
                        score = int(raw_score)
                    except (ValueError, TypeError):
                        score = 0
                    by_family[family].append((score, text))
        return dict(by_family)

    def _all_prompts(self) -> list[str]:
        """All prompts from market_questions.csv, sorted by influence score desc."""
        flat = []
        for prompts in self._by_family.values():
            flat.extend(prompts)
        flat.sort(key=lambda x: -x[0])
        return [text for _, text in flat]

    def _default_prompts(self) -> list[str]:
        if self._by_scenario:
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
