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
  ]
}

Do not include markdown.

Do not include explanations.

Do not wrap the JSON in code fences.

Return only the JSON object.
"""