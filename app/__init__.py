def __init__(self):
    self.dataset_manager = DatasetManager()
    self.provider_manager = ProviderManager()
    self.current_results = []
    self.current_summary = None
    self.current_insights = []
    self.current_relationships = []