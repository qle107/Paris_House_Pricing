"""Prompt templates for French planning document extraction (JSON output)."""

SYSTEM = (
    "Tu es analyste senior en investissement immobilier institutionnel. "
    "Tu lis des documents d'urbanisme francais (PLU, PLUi, SCoT, deliberations, "
    "concertations) et tu extrais UNIQUEMENT des faits verifiables, sans inventer. "
    "Reponds STRICTEMENT en JSON valide, sans texte autour."
)

EXTRACTION_TEMPLATE = """Contexte (extraits du document pour la commune {commune}) :
---
{context}
---
Extrais les signaux suivants s'ils sont presents. Pour chaque fait, donne une
citation courte (verbatim) et un niveau de confiance 0-1.

Renvoie un JSON de la forme:
{{
  "density_increase": [{{"description": "...", "zone": "...", "quote": "...", "confidence": 0.0}}],
  "rezoning":         [{{"from": "A|N|AU|U", "to": "AU|U", "secteur": "...", "quote": "...", "confidence": 0.0}}],
  "housing_target":   [{{"logements": 0, "horizon": "....", "quote": "...", "confidence": 0.0}}],
  "transport":        [{{"projet": "...", "mode": "metro|tram|rer|train|brt", "echeance": "....", "quote": "...", "confidence": 0.0}}],
  "redevelopment":    [{{"secteur": "...", "type": "ZAC|friche|reconversion", "quote": "...", "confidence": 0.0}}]
}}
Si une categorie est vide, renvoie une liste vide. N'invente aucun chiffre."""

RETRIEVAL_QUERIES = [
    "augmentation de la densite hauteur COS emprise au sol gabarit",
    "ouverture a l'urbanisation zone AU reclassement zonage",
    "objectifs de production de logements par an",
    "nouvelle gare metro tram desserte transport en commun",
    "ZAC operation d'amenagement friche reconversion renouvellement urbain",
]
