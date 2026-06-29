PRODUCT_PROMPTS = [
    "What should I know before buying a portable generator for home backup power?",
    "What are the most important features to compare when shopping for a portable generator?",
    "What is the difference between an inverter generator and a conventional generator?",
    "What wattage generator do I need to run essential appliances during a power outage?",
    "How do portable generators compare to whole-home standby generators for emergency backup?",
]

PERSONA_PROMPTS = [
    "Who typically buys portable generators and what do they use them for?",
    "What concerns do homeowners have when choosing a backup power generator?",
    "What do RV owners and campers look for in a portable generator?",
    "What motivates someone to finally buy a generator after thinking about it for a long time?",
]

JOURNEY_PROMPTS = [
    "How do people typically research which portable generator to buy?",
    "What questions should someone ask before purchasing a portable generator?",
    "Where do people buy portable generators and what review sources do they trust?",
    "What mistakes do people make when buying a portable generator?",
    "What factors cause buyers to choose one generator brand over another?",
]


class ProductAnalyst:
    name = "Product Intelligence"
    prompts = PRODUCT_PROMPTS


class PersonaAnalyst:
    name = "Consumer Personas"
    prompts = PERSONA_PROMPTS


class BuyingJourneyAnalyst:
    name = "Buying Journey"
    prompts = JOURNEY_PROMPTS
