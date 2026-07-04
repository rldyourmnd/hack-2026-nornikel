from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ENTITY_TYPES = (
    "material",
    "process",
    "regime",
    "condition",
    "property",
    "equipment",
    "facility",
    "experiment",
    "method",
    "team",
    "person",
    "expert",
    "laboratory",
    "organization",
    "location",
    "technology_solution",
    "economic_indicator",
    "conclusion",
    "recommendation",
    "limitation",
    "decision",
    "value",
    "publication",
    "patent",
    "standard",
)

EntityTypeLiteral = Literal[
    "material", "process", "regime", "condition", "property",
    "equipment", "facility", "experiment", "method", "team",
    "person", "expert", "laboratory", "organization", "location",
    "technology_solution", "economic_indicator", "conclusion",
    "recommendation", "limitation", "decision", "value",
    "publication", "patent", "standard",
]

RELATION_TYPES = (
    "MADE_OF",
    "USES_MATERIAL",
    "APPLIES_REGIME",
    "OPERATES_AT_CONDITION",
    "HAS_MEASUREMENT",
    "HAS_ECONOMIC_INDICATOR",
    "OF_PROPERTY",
    "PRODUCED_EFFECT",
    "PRODUCES_OUTPUT",
    "SHOWS_EFFECT",
    "USED_EQUIPMENT",
    "PERFORMED_BY",
    "AUTHORED_BY",
    "EXPERT_IN",
    "MEMBER_OF",
    "SUPPORTED_BY",
    "VALIDATED_BY",
    "FROM_DOCUMENT",
    "DERIVED_FROM",
    "CONTRADICTS",
    "HAS_LIMITATION",
    "RECOMMENDED_FOR",
    "SIMILAR_TO",
    "CONCLUDES",
    "DESCRIBED_IN",
)


class EntityMention(BaseModel):
    """A typed mention found in a span (GLiNER, LLM, or dictionary rules)."""

    text: str
    entity_type: EntityTypeLiteral
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
