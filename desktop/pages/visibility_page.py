from PySide6.QtWidgets import QLabel, QPushButton, QComboBox, QTextEdit, QVBoxLayout, QWidget

from backend.visibility.visibility_service import VisibilityService


class VisibilityPage(QWidget):
    def __init__(self, app):
        super().__init__()

        self.app = app
        self.service = VisibilityService(self.app.provider_manager)

        layout = QVBoxLayout()

        title = QLabel("Atlas Visibility")
        title.setStyleSheet("font-size:30px;font-weight:bold;")

        subtitle = QLabel("Run prompt sets against AI providers and store visibility responses.")
        subtitle.setStyleSheet("font-size:15px;color:#6B7280;")

        self.prompt_set = QComboBox()
        self.prompt_set.addItems(["default", "home backup", "rv"])

        self.provider = QComboBox()
        for provider_key in self.app.provider_manager.list_providers():
            self.provider.addItem(provider_key)

        run_button = QPushButton("Run Visibility Collection")
        run_button.clicked.connect(self.run_visibility)

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(QLabel("Prompt Set"))
        layout.addWidget(self.prompt_set)
        layout.addWidget(QLabel("Provider"))
        layout.addWidget(self.provider)
        layout.addWidget(run_button)
        layout.addWidget(QLabel("Visibility Results"))
        layout.addWidget(self.output)

        self.setLayout(layout)

        self.refresh_runs()

    def run_visibility(self):
        prompt_set = self.prompt_set.currentText()
        provider_name = self.provider.currentText()

        result = self.service.run(
            prompt_set=prompt_set,
            provider_name=provider_name
        )

        run = result["run"]

        self.output.setPlainText(
            f"Visibility run completed.\n\n"
            f"Run ID: {run.run_id}\n"
            f"Provider: {run.provider}\n"
            f"Model: {run.model}\n"
            f"Prompt Set: {run.prompt_set}\n"
            f"Responses: {run.response_count}\n"
            f"Duration: {run.duration_seconds:.2f} seconds\n\n"
        )

        self.refresh_runs()

    def refresh_analytics(self):
        summary = self.service.analytics_summary()

        text = "Visibility Analytics\n\n"
        text += f"Total Responses: {summary['total_responses']}\n"
        text += f"Firman Visibility Score: {summary['firman_visibility_score']}%\n\n"

        text += "First Mentioned Brand:\n"
        text += "Note: this is not treated as a recommendation. It only shows which brand appeared first in each response.\n"
        if summary["first_mentioned_brands"]:
            for brand, count in summary["first_mentioned_brands"].items():
                share = summary["first_mention_share"].get(brand, 0)
                text += f"• {brand}: {count} responses ({share}%)\n"
        else:
            text += "No first-mentioned brands found yet.\n"

        text += "\nFirman Visibility by Provider:\n"
        if summary["provider_visibility_scores"]:
            for provider, score in summary["provider_visibility_scores"].items():
                text += f"• {provider}: {score}%\n"
        else:
            text += "No provider visibility scores yet.\n"

        text += "\nFirman Visibility by Prompt Set:\n"
        if summary["prompt_set_visibility_scores"]:
            for prompt_set, score in summary["prompt_set_visibility_scores"].items():
                text += f"• {prompt_set}: {score}%\n"
        else:
            text += "No prompt set visibility scores yet.\n"

        text += "\nBrand Mentions:\n"
        if summary["brand_counts"]:
            for brand, count in summary["brand_counts"].items():
                text += f"• {brand}: {count}\n"
        else:
            text += "No brand mentions found yet.\n"

        text += "\nFeature Mentions:\n"
        if summary["feature_counts"]:
            for feature, count in summary["feature_counts"].items():
                text += f"• {feature}: {count}\n"
        else:
            text += "No feature mentions found yet.\n"

        text += "\nBrand Mentions by Provider:\n"

        if summary["provider_brand_counts"]:
            for provider, brands in summary["provider_brand_counts"].items():
                text += f"\n{provider}:\n"
                for brand, count in brands.items():
                    text += f"• {brand}: {count}\n"
        else:
            text += "No provider brand mentions found yet.\n"

        return text

    def refresh_runs(self):
        runs = self.service.list_runs() or []

        latest_run_id = runs[0][0] if runs else None
        latest_responses = (
            self.service.get_responses_for_run(latest_run_id)
            if latest_run_id
            else []
        )

        runs_text = "Recent Runs\n\n"

        if runs:
            for run in runs[:10]:
                runs_text += (
                    f"{run[4]} | {run[1]} | {run[3]} | "
                    f"{run[6]} | {run[7]} responses\n"
                )
        else:
            runs_text += "No visibility runs yet.\n"

        analytics_text = self.refresh_analytics()

        response_text = "\n\nLatest Run Responses:\n"

        if latest_responses:
            for response in latest_responses:
                response_text += (
                    f"\nPrompt: {response[4]}\n"
                    f"Response: {response[5][:500]}...\n"
                )
        else:
            response_text += "No responses available.\n"

        self.output.setPlainText(
            runs_text + "\n\n" + analytics_text + response_text
        )