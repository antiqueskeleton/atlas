from collections import Counter


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

        for response in responses:
            text = response[5].lower()

            for brand in self.BRANDS:
                if brand.lower() in text:
                    brand_counts[brand] += 1

            for feature in self.FEATURES:
                if feature.lower() in text:
                    feature_counts[feature] += 1

        return {
            "brand_counts": dict(brand_counts),
            "feature_counts": dict(feature_counts),
        }