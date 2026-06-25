from backend.analysts.brand_analyst import BrandAnalyst
from backend.analysts.feature_analyst import FeatureAnalyst


class AnalystRegistry:
    """
    Provides the analysts available to the orchestrator.

    This is the first step toward a plugin architecture.
    """

    @staticmethod
    def get_analysts(knowledge):
        return [
            BrandAnalyst(knowledge=knowledge),
            FeatureAnalyst(knowledge=knowledge),
        ]