from collections import Counter, defaultdict
from pathlib import Path

from backend.services.paths import get_data_dir


class VisibilityAnalytics:

    def __init__(
        self,
        brands_path=None,
        features_path=None,
        target_brand="",
    ):
        data_dir = get_data_dir()
        brands_path = brands_path or str(data_dir / "brands.csv")
        features_path = features_path or str(data_dir / "features.csv")
        self.target_brand = target_brand
        self.brands = self._load_terms(
            brands_path,
            fallback=[
                "Firman",
                "Champion",
                "Westinghouse",
                "Honda",
                "Generac",
                "Yamaha",
                "Predator",
            ]
        )

        self.features = self._load_terms(
            features_path,
            fallback=[
                "Dual Fuel",
                "Electric Start",
                "RV Ready",
                "Quiet",
                "Inverter",
                "Home Backup",
                "Portable",
                "Value",
            ]
        )

    def summarize_responses(self, responses):
        brand_counts = Counter()
        feature_counts = Counter()
        provider_brand_counts = defaultdict(Counter)
        provider_response_counts = Counter()
        prompt_set_brand_counts = defaultdict(Counter)
        prompt_set_response_counts = Counter()
        first_mentioned_brands = Counter()
        brand_position_counts = defaultdict(Counter)

        for response in responses:
            provider = response[2]
            prompt_set = response[7] if len(response) > 7 else "unknown"
            text = response[5].lower()

            provider_response_counts[provider] += 1
            prompt_set_response_counts[prompt_set] += 1

            mentioned_brands = []

            for brand in self.brands:
                brand_lower = brand.lower()

                if brand_lower in text:
                    brand_counts[brand] += 1
                    provider_brand_counts[provider][brand] += 1
                    prompt_set_brand_counts[prompt_set][brand] += 1
                    mentioned_brands.append((text.find(brand_lower), brand))

            if mentioned_brands:
                mentioned_brands.sort(key=lambda item: item[0])
                first_mentioned_brands[mentioned_brands[0][1]] += 1

                for index, (_, brand) in enumerate(mentioned_brands[:5], start=1):
                    brand_position_counts[index][brand] += 1

            for feature in self.features:
                if feature.lower() in text:
                    feature_counts[feature] += 1

        total_responses = len(responses)
        target = self.target_brand
        target_mentions = brand_counts.get(target, 0) if target else 0

        target_visibility_score = (
            round((target_mentions / total_responses) * 100, 1)
            if total_responses and target
            else 0
        )

        provider_visibility_scores = {}
        for provider, response_count in provider_response_counts.items():
            prov_target = provider_brand_counts[provider].get(target, 0) if target else 0
            provider_visibility_scores[provider] = (
                round((prov_target / response_count) * 100, 1)
                if response_count and target
                else 0
            )

        prompt_set_visibility_scores = {}
        for prompt_set, response_count in prompt_set_response_counts.items():
            ps_target = prompt_set_brand_counts[prompt_set].get(target, 0) if target else 0
            prompt_set_visibility_scores[prompt_set] = (
                round((ps_target / response_count) * 100, 1)
                if response_count and target
                else 0
            )

        first_mention_share = {}
        for brand, count in first_mentioned_brands.items():
            first_mention_share[brand] = (
                round((count / total_responses) * 100, 1)
                if total_responses
                else 0
            )

        brand_position_share = {}
        for position, counts in brand_position_counts.items():
            brand_position_share[position] = {}
            for brand, count in counts.items():
                brand_position_share[position][brand] = (
                    round((count / total_responses) * 100, 1)
                    if total_responses
                    else 0
                )

        return {
            "total_responses": total_responses,
            "target_brand": target,
            "target_visibility_score": target_visibility_score,
            "provider_visibility_scores": provider_visibility_scores,
            "prompt_set_visibility_scores": prompt_set_visibility_scores,
            "first_mentioned_brands": dict(first_mentioned_brands),
            "first_mention_share": first_mention_share,
            "brand_position_counts": {
                position: dict(counts)
                for position, counts in brand_position_counts.items()
            },
            "brand_position_share": brand_position_share,
            "brand_counts": dict(brand_counts),
            "feature_counts": dict(feature_counts),
            "provider_brand_counts": {
                provider: dict(counts)
                for provider, counts in provider_brand_counts.items()
            },
        }

    def _load_terms(self, path, fallback):
        file_path = Path(path)

        if not file_path.exists():
            return fallback

        terms = []

        for i, line in enumerate(file_path.read_text(encoding="utf-8").splitlines()):
            value = line.strip()

            if not value:
                continue

            if "," in value:
                value = value.split(",")[0].strip()

            if value.lower() in ["brand", "brands", "feature", "features", "name"]:
                continue

            if value:
                terms.append(value)

        return terms or fallback