from datetime import datetime
from pathlib import Path

from backend.services.knowledge_service import KnowledgeService
from backend.services.evidence_service import EvidenceService
from backend.services.dataset_manager import DatasetManager
from backend.services.config_service import ConfigService
from backend.registry.analyst_registry import AnalystRegistry
from backend.engines.insight_engine import InsightEngine
from backend.engines.relationship_engine import RelationshipEngine
from backend.models.run_summary import RunSummary
from backend.models.dataset import Dataset
from backend.ai.provider_manager import ProviderManager
from backend.volume.volume_provider_manager import VolumeProviderManager


class AtlasApplication:
    def __init__(self):
        # #92: rotating database backup at every launch (skipped when a
        # recent one exists). create_backup never raises — a backup problem
        # must not block startup; the Health card reports backup status.
        from backend.services.backup_service import create_backup
        create_backup()

        self.config_service = ConfigService()
        self.dataset_manager = DatasetManager()
        self.provider_manager = ProviderManager()
        self.volume_provider_manager = VolumeProviderManager()
        self._load_saved_keys()
        self._load_saved_volume_credentials()
        self.current_results = []
        self.current_summary = None
        self.current_insights = []
        self.current_relationships = []

    def _load_saved_keys(self):
        for key in self.provider_manager.list_providers():
            saved_key = self.config_service.get_api_key(key)
            if saved_key:
                self.provider_manager.set_provider_api_key(key, saved_key)
            saved_model = self.config_service.get_model(key)
            if saved_model:
                self.provider_manager.set_provider_model(key, saved_model)

    def _load_saved_volume_credentials(self):
        for key in self.volume_provider_manager.list_providers():
            saved_cred = self.config_service.get_volume_credential(key)
            if saved_cred:
                self.volume_provider_manager.set_provider_credential(key, saved_cred)
            saved_site = self.config_service.get_volume_site_url(key)
            if saved_site:
                self.volume_provider_manager.set_provider_site_url(key, saved_site)

    def get_target_brand(self) -> str:
        return self.config_service.get_target_brand()

    def analyze(self, response_file=None):
        knowledge_service = KnowledgeService()
        evidence_service = EvidenceService()

        knowledge = {
            "brands": knowledge_service.get_brands(),
            "features": knowledge_service.get_features(),
        }

        evidence = evidence_service.load_responses(response_file)

        dataset_name = "Default Sample Dataset"

        if response_file:
            dataset_name = Path(response_file).stem.replace("_", " ").title()

        dataset = Dataset(
            name=dataset_name,
            source="JSON Import" if response_file else "Default Sample",
            imported_at=datetime.now(),
            evidence=evidence,
        )

        self.dataset_manager.add_dataset(dataset)
        self.dataset_manager.set_active(dataset.name)

        return self.analyze_active_dataset(knowledge)

    def analyze_active_dataset(self, knowledge=None):
        knowledge_service = KnowledgeService()

        knowledge = knowledge or {
            "brands": knowledge_service.get_brands(),
            "features": knowledge_service.get_features(),
        }

        active_dataset = self.dataset_manager.get_active()

        if active_dataset is None:
            return None

        analysts = AnalystRegistry.get_analysts(knowledge)

        self.current_results = []

        for item in active_dataset.evidence:
            for analyst in analysts:
                self.current_results.append(analyst.analyze(item))

        self.current_summary = RunSummary(
            evidence_count=active_dataset.response_count,
            analyst_count=len(analysts),
            results=self.current_results
        ).build()

        insight_engine = InsightEngine()
        self.current_insights = insight_engine.generate(self.current_results)

        relationship_engine = RelationshipEngine()
        self.current_relationships = relationship_engine.generate(self.current_results)

        return {
            "dataset": active_dataset,
            "summary": self.current_summary,
            "insights": self.current_insights,
            "relationships": self.current_relationships,
            "results": self.current_results,
            "evidence": active_dataset.evidence,
            "datasets": self.dataset_manager.list_datasets(),
        }

    def analyze_from_visibility_db(self) -> dict | None:
        """
        Build the same analysis dict as analyze_active_dataset() but sourced
        entirely from the SQLite visibility_responses table.  No JSON import
        needed — works whenever Visibility has collected data.
        """
        from backend.visibility.visibility_repository import VisibilityRepository
        from backend.models.evidence import Evidence as EvidenceModel

        raw_responses = VisibilityRepository().list_responses()
        if not raw_responses:
            return None

        knowledge_service = KnowledgeService()
        knowledge = {
            "brands": knowledge_service.get_brands(),
            "features": knowledge_service.get_features(),
        }

        # Row: (id, run_id, provider, model, prompt, response, collected_at, prompt_set)
        evidence_list = [
            EvidenceModel(
                evidence_id=str(row[0]),
                source=row[2],
                text=row[5],
                prompt=row[4],
            )
            for row in raw_responses
        ]

        dataset = Dataset(
            name="Visibility Database",
            source="SQLite",
            imported_at=datetime.now(),
            evidence=evidence_list,
        )

        analysts = AnalystRegistry.get_analysts(knowledge)
        results = []
        for item in evidence_list:
            for analyst in analysts:
                results.append(analyst.analyze(item))

        summary = RunSummary(
            evidence_count=len(evidence_list),
            analyst_count=len(analysts),
            results=results,
        ).build()

        insight_engine = InsightEngine()
        insights = insight_engine.generate(results)

        relationship_engine = RelationshipEngine()
        relationships = relationship_engine.generate(results)

        return {
            "dataset": dataset,
            "summary": summary,
            "insights": insights,
            "relationships": relationships,
            "results": results,
            "evidence": evidence_list,
            "datasets": self.dataset_manager.list_datasets(),
        }

    def has_analysis(self):
        return self.current_summary is not None

    def list_datasets(self):
        return self.dataset_manager.list_datasets()