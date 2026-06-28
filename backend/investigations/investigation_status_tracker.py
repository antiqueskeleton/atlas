from backend.investigations.investigation_status import InvestigationStatus


class InvestigationStatusTracker:

    def __init__(self):
        self.status = InvestigationStatus(
            current_step="Idle",
            progress=0
        )

    def update(self, step, progress):
        self.status.current_step = step
        self.status.progress = progress

    def current(self):
        return self.status