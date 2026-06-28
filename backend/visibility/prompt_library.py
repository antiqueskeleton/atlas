class PromptLibrary:
    def default_prompts(self):
        return [
            "What is the best portable generator for home backup?",
            "What is the best portable generator for RV camping?",
            "Which generator brands are most reliable?",
            "What is the best dual fuel portable generator?",
            "Which portable generator is the best value?",
        ]

    def home_backup_prompts(self):
        return [
            "What is the best portable generator for home backup?",
            "Which generator brand is best for emergency backup power?",
            "What portable generator should I buy for power outages?",
            "Which generator is best for running home essentials?",
            "Compare Firman, Champion, Westinghouse, Honda, and Generac for home backup.",
        ]

    def rv_prompts(self):
        return [
            "What is the best generator for RV camping?",
            "Which portable generator is best for RV use?",
            "What quiet generator should I buy for camping?",
            "Compare Firman, Champion, Honda, Yamaha, and Westinghouse for RV camping.",
            "Which inverter generator is best for an RV?",
        ]

    def get(self, prompt_set):
        prompt_set = prompt_set.lower().strip()

        if prompt_set == "home backup":
            return self.home_backup_prompts()

        if prompt_set == "rv":
            return self.rv_prompts()

        return self.default_prompts()