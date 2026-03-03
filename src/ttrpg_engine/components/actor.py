"""Actor-related components."""

from __future__ import annotations

from dataclasses import dataclass


class ActorComponent:
    """Marker base class for actor-like components across systems."""


@dataclass(frozen=True)
class NarrativeActor(ActorComponent):
    name: str
    kind: str = "npc"


@dataclass(frozen=True)
class ScenePresence:
    scene_id: str


@dataclass(frozen=True)
class LongTermGoals:
    goals: tuple[str, ...]


@dataclass(frozen=True)
class FactionRelations:
    standings: dict[str, int]


@dataclass(frozen=True)
class ActorAgency:
    possible_goals: tuple[str, ...] = ()
    short_term_goal: str = ""
    impulse: str = ""
    last_impulse_turn: int = -1


@dataclass(frozen=True)
class ActorImpulse:
    actor_entity_id: int
    turn_id: int
    scene_id: str
    goal: str
    impulse: str
