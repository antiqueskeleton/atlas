from collections import Counter, defaultdict


class VisibilityAnalytics:

    BRANDS = [
        "Firman",
        "Champion",
        "Westinghouse",
        "Honda",
        "Generac",
        "Yamaha",
        "Predator",
    ]

    FEATURES = [
        "Dual Fuel",
        "Electric Start",
        "RV Ready",
        "Quiet",
        "Inverter",
        "Home Backup",
        "Portable",
        "Value",
    ]

    def summarize_responses(self, responses):

        brand_counts = Counter()
        feature_counts = Counter()
        provider_brand_counts = defaultdict(Counter)
        provider_response_counts = Counter()
        prompt_set_brand_counts = defaultdict(Counter)
        prompt_set_response_counts = Counter()
        recommendation_leaders = Counter()

        for response in responses:

            provider = response[2]
            prompt_set = response[7] if len(response) > 7 else "unknown"
            text_original = response[5]
            text = text_original.lower()

            provider_response_counts[provider] += 1
            prompt_set_response_counts[prompt_set] += 1

            mentioned_brands = []

            for brand in self.BRANDS:
                if brand.lower() in text:
                    brand_counts[brand] += 1
                    provider_brand_counts[provider][brand] += 1
                    prompt_set_brand_counts[prompt_set][brand] += 1
                    mentioned_brands.append((text.find(brand.lower()), brand))

            if mentioned_brands:
                mentioned_brands.sort(key=lambda item: item[0])
                recommendation_leaders[mentioned_brands[0][1]] += 1

            for feature in self.FEATURES:
                if feature.lower() in text:
                    feature_counts[feature] += 1

        total_responses = len(responses)
        firman_mentions = brand_counts.get("Firman", 0)

        firman_visibility_score = (
            round((firman_mentions / total_responses) * 100, 1)
            if total_responses
            else 0
        )

        provider_visibility_scores = {}

        for provider, response_count in provider_response_counts.items():
            provider_firman_mentions = provider_brand_counts[provider].get("Firman", 0)

            provider_visibility_scores[provider] = (
                round((provider_firman_mentions / response_count) * 100, 1)
                if response_count
                else 0
            )

        prompt_set_visibility_scores = {}

        for prompt_set, response_count in prompt_set_response_counts.items():
            prompt_set_firman_mentions = prompt_set_brand_counts[prompt_set].get("Firman", 0)

            prompt_set_visibility_scores[prompt_set] = (
                round((prompt_set_firman_mentions / response_count) * 100, 1)
                if response_count
                else 0
            )

        recommendation_share = {}

        for brand, count in recommendation_leaders.items():
            recommendation_share[brand] = (
                round((count / total_responses) * 100, 1)
                if total_responses
                else 0
            )

        return {
            "total_responses": total_responses,
            "firman_visibility_score": firman_visibility_score,
            "provider_visibility_scores": provider_visibility_scores,
            "prompt_set_visibility_scores": prompt_set_visibility_scores,
            "recommendation_leaders": dict(recommendation_leaders),
            "recommendation_share": recommendation_share,
            "brand_counts": dict(brand_counts),
            "feature_counts": dict(feature_counts),
            "provider_brand_counts": {
                provider: dict(counts)
                for provider, counts in provider_brand_counts.items()
            },
        }