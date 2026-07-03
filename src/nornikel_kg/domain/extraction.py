from __future__ import annotations

from pydantic import BaseModel, Field

ENTITY_TYPES = (
    "material",
    "regime",
    "property",
    "equipment",
    "team",
    "person",
    "laboratory",
    "conclusion",
    "decision",
    "value",
    "publication",
)

RELATION_TYPES = (
    "MADE_OF",
    "APPLIES_REGIME",
    "HAS_MEASUREMENT",
    "OF_PROPERTY",
    "PRODUCED_EFFECT",
    "USED_EQUIPMENT",
    "PERFORMED_BY",
    "AUTHORED_BY",
    "SUPPORTED_BY",
    "FROM_DOCUMENT",
    "DERIVED_FROM",
    "CONTRADICTS",
    "CONCLUDES",
    "DESCRIBED_IN",
)


class EntityMention(BaseModel):
    """A typed mention found in a span (GLiNER, LLM, or dictionary rules)."""

    text: str
    entity_type: str
    start: int = 0
    end: int = 0
    confidence: float = 1.0
    origin: str = "rule"


class ExtractedRelation(BaseModel):
    src_text: str
    src_type: str
    relation_type: str
    dst_text: str
    dst_type: str
    confidence: float = 1.0


class ExtractionPayload(BaseModel):
    """LLM guided-JSON extraction contract for one span batch."""

    entities: list[EntityMention] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)


# Strict-mode contract (OpenAI-compatible providers): every key present in
# `properties` MUST be listed in `required`, otherwise the request itself is
# rejected. Confidence is therefore assigned in code, not requested from the
# model — weak models reliably emit the required-only shape.
EXTRACTION_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "entity_type": {"type": "string", "enum": list(ENTITY_TYPES)},
                },
                "required": ["text", "entity_type"],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "src_text": {"type": "string"},
                    "src_type": {"type": "string", "enum": list(ENTITY_TYPES)},
                    "relation_type": {"type": "string", "enum": list(RELATION_TYPES)},
                    "dst_text": {"type": "string"},
                    "dst_type": {"type": "string", "enum": list(ENTITY_TYPES)},
                },
                "required": ["src_text", "src_type", "relation_type", "dst_text", "dst_type"],
            },
        },
    },
    "required": ["entities", "relations"],
}
