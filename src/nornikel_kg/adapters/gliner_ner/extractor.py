from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

from nornikel_kg.domain.extraction import EntityMention

logger = logging.getLogger(__name__)

# Evidence-based decision (2026-07-03, plans/09): GLiNER2 rejected for RU
# (English-only training, no RU benchmarks, broken relation extraction);
# gliner_multi-v2.1 stays — same multilingual mdeberta-v3-base backbone.
_MODEL_ID = "urchade/gliner_multi-v2.1"

# Zero-shot labels in both languages; GLiNER maps them onto our entity types.
_LABELS: dict[str, str] = {
    "material": "material",
    "сплав": "material",
    "processing regime": "regime",
    "режим обработки": "regime",
    "material property": "property",
    "свойство материала": "property",
    "equipment": "equipment",
    "оборудование": "equipment",
    "team": "team",
    "команда": "team",
    "person": "person",
    "laboratory": "laboratory",
    "conclusion": "conclusion",
    "решение": "decision",
}

_CHUNK_CHARS = 1500
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")


def sentence_chunks(text: str, max_chars: int = _CHUNK_CHARS) -> list[tuple[int, str]]:
    """(offset, chunk) pairs split on sentence boundaries with 1-sentence overlap.

    A hard character cut («text[0:1500]») slices entities in half at every
    chunk edge; sentence-aligned chunks with overlap keep boundary entities
    intact, and the caller dedupes by global offsets.
    """
    if len(text) <= max_chars:
        return [(0, text)] if text.strip() else []
    sentences: list[tuple[int, str]] = []
    cursor = 0
    for part in _SENTENCE_SPLIT_RE.split(text):
        start = text.index(part, cursor)
        sentences.append((start, part))
        cursor = start + len(part)
    if not sentences:
        return [(0, text)]

    chunks: list[tuple[int, str]] = []
    index = 0
    while index < len(sentences):
        chunk_start = sentences[index][0]
        end_index = index
        while (
            end_index + 1 < len(sentences)
            and sentences[end_index + 1][0]
            + len(sentences[end_index + 1][1])
            - chunk_start
            <= max_chars
        ):
            end_index += 1
        # Oversized single sentence: fall back to a hard slice for it alone.
        if end_index == index and len(sentences[index][1]) > max_chars:
            sentence_start, sentence_text = sentences[index]
            for offset in range(0, len(sentence_text), max_chars):
                chunks.append(
                    (sentence_start + offset, sentence_text[offset : offset + max_chars])
                )
            index += 1
            continue
        chunk_end = sentences[end_index][0] + len(sentences[end_index][1])
        chunks.append((chunk_start, text[chunk_start:chunk_end]))
        if end_index + 1 >= len(sentences):
            break
        # Overlap: the next chunk restarts from the last sentence of this one
        # (unless the chunk held a single sentence — then just advance).
        index = end_index if end_index > index else index + 1
    return chunks


@lru_cache(maxsize=1)
def _load_model() -> Any:
    from gliner import GLiNER

    logger.info("Loading GLiNER model %s", _MODEL_ID)
    return GLiNER.from_pretrained(_MODEL_ID)


class GLiNERMentionExtractor:
    """Zero-shot multilingual NER pre-pass (cheap, no LLM)."""

    threshold = 0.35

    def extract(self, text: str) -> list[EntityMention]:
        model = _load_model()
        best: dict[tuple[int, int, str], EntityMention] = {}
        for offset, chunk in sentence_chunks(text):
            for prediction in model.predict_entities(
                chunk, list(_LABELS.keys()), threshold=self.threshold
            ):
                label = str(prediction.get("label", ""))
                entity_type = _LABELS.get(label)
                if entity_type is None:
                    continue
                start = int(prediction.get("start", 0)) + offset
                end = int(prediction.get("end", 0)) + offset
                mention = EntityMention(
                    text=str(prediction.get("text", "")).strip(),
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    confidence=float(prediction.get("score", 0.0)),
                    origin="gliner",
                )
                key = (start, end, entity_type)
                if key not in best or mention.confidence > best[key].confidence:
                    best[key] = mention
        return list(best.values())
