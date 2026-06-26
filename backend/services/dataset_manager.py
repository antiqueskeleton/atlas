from backend.models.dataset import Dataset


class DatasetManager:
    def __init__(self):
        self.datasets = []
        self.active_dataset = None

    def add_dataset(self, dataset: Dataset):
        self.datasets.append(dataset)

        if self.active_dataset is None:
            self.active_dataset = dataset

    def set_active(self, dataset_name: str):
        for dataset in self.datasets:
            if dataset.name == dataset_name:
                self.active_dataset = dataset
                return dataset

        return None

    def get_active(self):
        return self.active_dataset

    def list_datasets(self):
        return self.datasets