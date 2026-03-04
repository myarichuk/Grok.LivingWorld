"""Actor-related components."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActorComponent:
    """Marker base class for actor-like components across systems."""


@dataclass(frozen=True)
class NarrativeActor(ActorComponent):
    name: str
    kind: str = "npc"


@dataclass(frozen=True)
class ScenePresence:
    scene_id: str


class DistanceBucket(str, Enum):
    """Coarse tactical distance from a scene-local reference point."""

    ENGAGED = "engaged"
    CLOSE = "close"
    NEAR = "near"
    FAR = "far"
    DISTANT = "distant"


@dataclass(frozen=True)
class ScenePosition:
    """Actor position within a scene by zone and relative distance bucket."""

    scene_id: str
    zone: str = "default"
    distance_bucket: DistanceBucket = DistanceBucket.NEAR


@dataclass(frozen=True)
class LongTermGoals:
    goals: tuple[str, ...]


@dataclass(frozen=True)
class FactionRelations:
    standings: dict[str, int]


@dataclass(frozen=True)
class FactionTraits:
    traits: tuple[str, ...]


@dataclass(frozen=True)
class ActorAgency:
    possible_goals: tuple[str, ...] = ()
    short_term_goal: str = ""
    impulse: str = ""
    last_impulse_turn: int = -1


@dataclass(frozen=True)
class InitiativeState:
    """Tracks how many turns passed since this actor's last impulse."""

    min_turns_between_impulses: int = 1
    turns_since_last_impulse: int = 9999
    last_impulse_turn: int = -1


@dataclass(frozen=True)
class CurrentAction:
    """Most recent known action this actor is currently taking."""

    description: str
    source: str
    turn_id: int


@dataclass(frozen=True)
class ActionRecord:
    turn_id: int
    action: str
    source: str
    note: str = ""


@dataclass(frozen=True)
class ActionHistory:
    records: tuple[ActionRecord, ...] = ()


@dataclass(frozen=True)
class ActorImpulse:
    actor_entity_id: int
    turn_id: int
    scene_id: str
    goal: str
    impulse: str
    zone: str = "default"
    distance_bucket: DistanceBucket = DistanceBucket.NEAR


@dataclass(frozen=True)
class EnvironmentImpulse:
    """Background impulse for distant actors in the same scene."""

    actor_entity_id: int
    turn_id: int
    scene_id: str
    zone: str
    distance_bucket: DistanceBucket
    summary: str
