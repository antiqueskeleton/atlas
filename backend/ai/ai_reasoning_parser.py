from backend.models.ai_reasoning import AIReasoning


class AIReasoningParser:
    def parse(self, text: str, provider: str) -> AIReasoning:
        sections = self._extract_sections(text)

        return AIReasoning(
            executive_summary=sections.get("executive_summary", text).strip(),
            confidence=sections.get("confidence", "Medium").strip(),
            opportunities=self._to_list(sections.get("opportunities", "")),
            risks=self._to_list(sections.get("risks", "")),
            follow_up_questions=self._to_list(sections.get("follow_up_questions", "")),
            provider=provider,
        )

    def _extract_sections(self, text: str):
        section_map = {
            "executive summary:": "executive_summary",
            "opportunities:": "opportunities",
            "risks:": "risks",
            "follow-up questions:": "follow_up_questions",
            "follow up questions:": "follow_up_questions",
            "confidence:": "confidence",
        }

        sections = {}
        current_key = None
        current_lines = []

        for line in text.splitlines():
            normalized = line.strip().lower()

            if normalized in section_map:
                if current_key:
                    sections[current_key] = "\n".join(current_lines).strip()

                current_key = section_map[normalized]
                current_lines = []
            else:
                if current_key:
                    current_lines.append(line)

        if current_key:
            sections[current_key] = "\n".join(current_lines).strip()

        return sections

    def _to_list(self, text: str):
        items = []

        for line in text.splitlines():
            cleaned = line.strip()

            if not cleaned:
                continue

            cleaned = cleaned.lstrip("-•0123456789. ").strip()

            if cleaned:
                items.append(cleaned)

        return items