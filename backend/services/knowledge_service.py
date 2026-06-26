from typing import List


class KnowledgeService:
    """
    Central access point for Atlas knowledge.

    Analysts should ask this service for curated knowledge instead of
    knowing whether data comes from Python lists, CSV files, SQLite, or APIs.
    """

    def get_brands(self) -> List[str]:
        return [
            "Firman",
            "Champion",
            "Honda",
            "Westinghouse",
            "Generac",
            "Predator",
            "DuroMax",
            "Yamaha",
            "EcoFlow",
            "Jackery",
            "Bluetti",
            "Goal Zero",
            "Anker",
        ]

    def get_features(self) -> List[str]:
        return [
            "Dual Fuel",
            "Tri Fuel",
            "Gasoline",
            "Propane",
            "Natural Gas",
            "Inverter",
            "Open Frame",
            "Electric Start",
            "Remote Start",
            "CO Shutoff",
            "Low THD",
            "Parallel Capable",
            "Quiet Operation",
            "Long Runtime",
            "RV Ready",
            "Home Backup"
        ]