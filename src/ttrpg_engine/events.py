"""Domain events published through ECS world pub/sub broker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActorImpulseEvent:
    actor_entity_id: int
    target_entity_id: int | None
    scene_id: str
    turn_id: int
    impulse: str
    source: str


@dataclass(frozen=True)
class ActorRegisteredEvent:
    actor_entity_id: int
    actor_name: str
    scene_id: str
    long_term_goals: tuple[str, ...]
    faction_relations: dict[str, int]
    source: str = "llm_gateway"
