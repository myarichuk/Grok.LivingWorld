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


@dataclass(frozen=True)
class FactionUpdatedEvent:
    faction_entity_id: int
    faction_name: str
    heat: int
    flags: tuple[str, ...]
    source: str = "llm_faction_gateway"


@dataclass(frozen=True)
class PlayerActionEvent:
    player_entity_id: int
    turn_id: int
    action: str
    intent: str
    target_entity_id: int | None
    source: str
