from backend.models.evidence_citation import EvidenceCitation


class EvidenceCitationBuilder:

    def build(self, evidence_list, citation_numbers):
        citations = []

        for number in citation_numbers:
            index = number - 1

            if 0 <= index < len(evidence_list):
                evidence = evidence_list[index]

                citations.append(
                    EvidenceCitation(
                        number=number,
                        source=evidence.source,
                        prompt=evidence.prompt,
                        preview=evidence.text[:180]
                    )
                )

        return citations