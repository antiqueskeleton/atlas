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

        for response in responses:
            provider = response[2]
            text = response[5].lower()

            for brand in self.BRANDS:
                if brand.lower() in text:
                    brand_counts[brand] += 1
                    provider_brand_counts[provider][brand] += 1

            for feature in self.FEATURES:
                if feature.lower() in text:
                    feature_counts[feature] += 1

        return {
            "brand_counts": dict(brand_counts),
            "feature_counts": dict(feature_counts),
            "provider_brand_counts": {
                provider: dict(counts)
                for provider, counts in provider_brand_counts.items()
            },
        }