"""Actor-related components."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActorComponent:
    """Marker base class for actor-like components across systems."""


class NpcResidencyType(str, Enum):
    """Lifecycle category for NPC persistence and cleanup behavior."""

    TRANSIENT = "transient"
    PERSISTENT = "persistent"


class ActorDetailMode(str, Enum):
    """Data density mode for actor records."""

    FULL_PROFILE = "full_profile"
    STAT_BLOCK = "stat_block"


@dataclass(frozen=True)
class NpcLifecycle:
    """Lifecycle and narrative-visibility metadata for NPCs."""

    residency_type: NpcResidencyType = NpcResidencyType.PERSISTENT
    spawn_turn_id: int = -1
    last_seen_turn_id: int = -1
    transient_timeout_turns: int = 6
    known_to_pc: bool = False
    tags: tuple[str, ...] = ()


class RelationshipBucket(str, Enum):
    """Coarse relationship category for graph queries and narrative tone."""

    HATER = "hater"
    ENEMY = "enemy"
    RIVAL = "rival"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    ALLY = "ally"
    TRUSTED = "trusted"


@dataclass(frozen=True)
class RelationshipEdge:
    """Directed relationship edge persisted in ECS storage."""

    source_actor_entity_id: int
    target_actor_entity_id: int
    bucket: RelationshipBucket = RelationshipBucket.ACQUAINTANCE
    score: int = 0
    tags: tuple[str, ...] = ()
    query_tags: tuple[str, ...] = ()
    last_updated_turn_id: int = -1
    visibility: str = "private"
    known_to_pc: bool = False


@dataclass(frozen=True)
class ActorPresentation:
    """Narrative-facing descriptors for varied non-gamey references."""

    description: str = ""
    notable_traits: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActorStatBlock:
    """Compact combat profile for swarm or lightweight actors."""

    stat_block_name: str = ""
    stat_block_source: str = ""
    role: str = ""
    challenge_rating: str = ""
    max_hit_points: int = 1
    current_hit_points: int = 1
    armor_class: int = 10
    speed: int = 30
    attack_bonus: int = 0
    damage_hint: str = ""
    perception: int = 10
    senses: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()


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
