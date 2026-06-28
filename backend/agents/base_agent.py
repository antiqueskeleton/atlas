from abc import ABC, abstractmethod


class BaseAgent(ABC):

    @property
    @abstractmethod
    def task_name(self):
        ...

    @abstractmethod
    def run(self, analysis, request=None):
        ...