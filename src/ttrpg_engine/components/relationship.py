"""Relationship memory components for directed, emotionally weighted history."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RelationshipMemory:
    """Directed relationship state and key emotional memories."""

    trust: int = 0
    affection: int = 0
    fear: int = 0
    resentment: int = 0
    key_events: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    last_meaningful_interaction_turn: int = -1


@dataclass(frozen=True)
class RelationshipMemoryLink:
    """Identifies the directed source/target pair for a relationship memory."""

    source_actor_entity_id: int
    target_actor_entity_id: int
