from __future__ import annotations

from typing import Protocol

from nornikel_kg.domain.extraction import EntityMention


class MentionExtractorPort(Protocol):
    def extract(self, text: str) -> list[EntityMention]:
        """Extract typed entity mentions with character offsets from text."""
