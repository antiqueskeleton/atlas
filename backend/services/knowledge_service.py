from backend.knowledge.knowledge_repository import KnowledgeRepository


class KnowledgeService:
    """
    Central access point for Atlas knowledge.

    Reads live from the database so brand/feature additions in the Knowledge
    page are immediately available to analysts and visibility runs.
    """

    def __init__(self):
        self._repo = KnowledgeRepository()

    def get_brands(self) -> list[str]:
        return [name for _, name, *_ in self._repo.list_brands()]

    def get_features(self) -> list[str]:
        return [name for _, name, *_ in self._repo.list_features()]
