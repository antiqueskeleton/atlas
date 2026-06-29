import csv
from collections import Counter, defaultdict
from pathlib import Path

from backend.services.paths import get_data_dir


class VisibilityAnalytics:

    def __init__(
        self,
        brands_path=None,
        features_path=None,
        channels_path=None,
        target_brand="",
    ):
        data_dir = get_data_dir()
        features_path = features_path or str(data_dir / "features.csv")
        channels_path = channels_path or str(data_dir / "channels.csv")
        self.target_brand = target_brand

        # Load brands from DB (brands_path kept for backwards compat but ignored when DB has data)
        from backend.knowledge.knowledge_repository import KnowledgeRepository
        brand_terms = KnowledgeRepository().get_brand_detection_terms()
        if brand_terms:
            self.brands = list(brand_terms.keys())
            self.brand_terms = brand_terms
        else:
            fallback = ["Firman", "Champion", "Westinghouse", "Honda", "Generac", "Yamaha", "Predator"]
            self.brands = self._load_terms(
                brands_path or str(data_dir / "brands.csv"),
                fallback=fallback,
            )
            self.brand_terms = {b: [b.lower()] for b in self.brands}

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

        self.channels = self._load_channels(channels_path)

    def summarize_responses(self, responses):
        brand_counts = Counter()
        feature_counts = Counter()
        provider_brand_counts = defaultdict(Counter)
        provider_response_counts = Counter()
        prompt_set_brand_counts = defaultdict(Counter)
        prompt_set_response_counts = Counter()
        first_mentioned_brands = Counter()
        brand_position_counts = defaultdict(Counter)
        channel_counts = Counter()
        brand_channel_counts: dict[str, Counter] = defaultdict(Counter)
        channel_brand_counts: dict[str, Counter] = defaultdict(Counter)

        for response in responses:
            provider = response[2]
            prompt_set = response[7] if len(response) > 7 else "unknown"
            text = response[5].lower()

            provider_response_counts[provider] += 1
            prompt_set_response_counts[prompt_set] += 1

            mentioned_brands = []

            for brand in self.brands:
                search_terms = self.brand_terms.get(brand, [brand.lower()])
                positions = [text.find(t) for t in search_terms if text.find(t) >= 0]
                if positions:
                    match_pos = min(positions)
                    brand_counts[brand] += 1
                    provider_brand_counts[provider][brand] += 1
                    prompt_set_brand_counts[prompt_set][brand] += 1
                    mentioned_brands.append((match_pos, brand))

            if mentioned_brands:
                mentioned_brands.sort(key=lambda item: item[0])
                first_mentioned_brands[mentioned_brands[0][1]] += 1

                for index, (_, brand) in enumerate(mentioned_brands[:5], start=1):
                    brand_position_counts[index][brand] += 1

            for feature in self.features:
                if feature.lower() in text:
                    feature_counts[feature] += 1

            # Channel co-occurrence: track which channels appear alongside which brands
            brand_names_in_response = [b for _, b in mentioned_brands]
            for ch_name, ch_terms, _ in self.channels:
                if any(t in text for t in ch_terms):
                    channel_counts[ch_name] += 1
                    for brand in brand_names_in_response:
                        brand_channel_counts[brand][ch_name] += 1
                        channel_brand_counts[ch_name][brand] += 1

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

        # Channel gap: channels where competitors appear more than Firman
        firman_channel_gap = []
        if target:
            for ch_name, _, _ in self.channels:
                firman_count = brand_channel_counts[target].get(ch_name, 0)
                competitor_counts = {
                    b: brand_channel_counts[b].get(ch_name, 0)
                    for b in self.brands
                    if b != target and brand_channel_counts[b].get(ch_name, 0) > 0
                }
                if competitor_counts:
                    top_competitor = max(competitor_counts, key=competitor_counts.get)
                    top_count = competitor_counts[top_competitor]
                    if top_count > firman_count:
                        firman_channel_gap.append({
                            "channel": ch_name,
                            "firman_count": firman_count,
                            "top_competitor": top_competitor,
                            "top_competitor_count": top_count,
                            "total_competitor_mentions": sum(competitor_counts.values()),
                        })
            firman_channel_gap.sort(key=lambda x: -x["total_competitor_mentions"])

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
            "channel_counts": dict(channel_counts),
            "brand_channel_counts": {b: dict(c) for b, c in brand_channel_counts.items()},
            "channel_brand_counts": {ch: dict(b) for ch, b in channel_brand_counts.items()},
            "firman_channel_gap": firman_channel_gap,
        }

    def _load_channels(self, path) -> list[tuple[str, list[str], str]]:
        """Return list of (name, [search_terms], category) from channels.csv."""
        file_path = Path(path)
        if not file_path.exists():
            return []
        channels = []
        with file_path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                name = row.get("name", "").strip()
                raw_terms = row.get("terms", "").strip()
                category = row.get("category", "").strip()
                if name and raw_terms:
                    terms = [t.strip().lower() for t in raw_terms.split(";") if t.strip()]
                    channels.append((name, terms, category))
        return channels

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