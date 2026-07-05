RESPONSE_SCHEMA = """
Return ONLY valid JSON.

Use exactly this structure:

{
  "executive_summary": "string",
  "confidence": "High | Medium | Low",
  "opportunities": [
    "string"
  ],
  "risks": [
    "string"
  ],
  "follow_up_questions": [
    "string"
  ],
  "supporting_evidence": [
    1,
    2,
    3
  ]
}

The supporting_evidence array should contain the numbered evidence items you used when forming your conclusion.

Grounding rules (Atlas is a factual analytics tool, not a marketing copywriter):

- Base every claim ONLY on the Dataset Summary and Supporting Evidence provided above.
- Do NOT introduce outside facts about corporate ownership, partnerships, mergers,
  acquisitions, or relationships between brands unless they are explicitly stated in the
  evidence provided. If you are not certain something is true from the evidence given,
  do not state it as fact.
- Every specific factual claim in executive_summary, opportunities, and risks should be
  traceable to one of the numbered evidence items or the Dataset Summary counts — not to
  general industry knowledge you may have from training.

Do not include markdown.

Do not include explanations.

Do not wrap the JSON in code fences.

Return only the JSON object.
"""