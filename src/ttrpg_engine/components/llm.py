"""LLM-facing command and response components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StartTurnCommand:
    request_type: str
    context: dict[str, Any] = field(default_factory=dict)
    schema: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"
    advance_minutes: int = 10


@dataclass(frozen=True)
class EndTurnCommand:
    pass


@dataclass(frozen=True)
class NeedsLLMFill:
    request_id: str
    turn_id: int
    request_type: str
    context: dict[str, Any]
    schema: dict[str, Any]
    schema_version: str
    needs_llm: bool = True


@dataclass(frozen=True)
class LLMResponse:
    request_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ResolvedLLMResult:
    request_id: str
    request_type: str
    turn_id: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class LLMActorRegistrationCommand:
    """LLM-provided registration/update payload for NPC agency setup."""

    actor_name: str
    scene_id: str
    long_term_goals: tuple[str, ...]
    faction_relations: dict[str, int]
    scene_zone: str = "default"
    scene_distance_bucket: str = "near"
    faction_entity_id: int | None = None
    faction_traits: tuple[str, ...] = ()
    possible_goals: tuple[str, ...] = ()
    actor_entity_id: int | None = None
    actor_kind: str = "llm_npc"
    suggested_impulse: str = ""
    current_action: str = ""
    turns_since_last_impulse: int | None = None
    min_turns_between_impulses: int = 1
    residency_type: str = "persistent"
    known_to_pc: bool = False
    transient_timeout_turns: int = 6
    npc_tags: tuple[str, ...] = ()
    detail_mode: str = "full_profile"
    description: str = ""
    notable_traits: tuple[str, ...] = ()
    actor_tags: tuple[str, ...] = ()
    stat_block_name: str = ""
    stat_block_source: str = ""
    stat_block_role: str = ""
    stat_block_challenge_rating: str = ""
    stat_block_max_hit_points: int = 1
    stat_block_armor_class: int = 10
    stat_block_speed: int = 30
    stat_block_attack_bonus: int = 0
    stat_block_damage_hint: str = ""
    stat_block_perception: int = 10
    stat_block_senses: tuple[str, ...] = ()
    stat_block_languages: tuple[str, ...] = ()


@dataclass(frozen=True)
class LLMFactionUpdateCommand:
    """LLM-provided faction update payload (heat, clocks, goals, flags)."""

    faction_name: str
    faction_entity_id: int | None = None
    heat: int = 0
    flags: tuple[str, ...] = ()
    global_goals: tuple[str, ...] = ()
    regional_goals: dict[str, tuple[str, ...]] = field(default_factory=dict)
    grand_plan_name: str = "grand_plan"
    grand_plan_progress: float = 0.0
    grand_plan_max_progress: float = 100.0
    grand_plan_rate_per_turn: float = 1.0


@dataclass(frozen=True)
class LLMPlayerAgencyCommand:
    """LLM-provided player agency decision/action payload for a turn."""

    player_entity_id: int
    action: str
    intent: str = ""
    target_entity_id: int | None = None


@dataclass(frozen=True)
class LLMPromoteTransientNpcCommand:
    """Promote a transient NPC into persistent world state."""

    actor_entity_id: int
    promoted_name: str = ""
    known_to_pc: bool = True
    tags_to_add: tuple[str, ...] = ()


@dataclass(frozen=True)
class LLMQueryTransientInteractionsCommand:
    """Query transient NPC interaction history for promotion decisions."""

    pc_entity_id: int | None = None
    scene_id: str = ""
    turn_min: int = -1
    turn_max: int = -1
    include_already_known: bool = True


@dataclass(frozen=True)
class LLMTransientInteractionQueryResult:
    """Result payload for transient-interaction query command."""

    command_entity_id: int
    candidates: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class LLMRelationshipUpsertCommand:
    """Create or update one directed relationship edge."""

    source_actor_entity_id: int
    target_actor_entity_id: int
    bucket: str
    score: int = 0
    tags: tuple[str, ...] = ()
    visibility: str = "private"
    known_to_pc: bool = False


@dataclass(frozen=True)
class LLMRelationshipQueryCommand:
    """Query relationship graph edges by actor/bucket/tag filters."""

    actor_entity_id: int
    bucket: str = ""
    tag: str = ""
    include_outgoing: bool = True
    include_incoming: bool = True


@dataclass(frozen=True)
class LLMRelationshipQueryResult:
    """Result payload for relationship graph query command."""

    command_entity_id: int
    edges: tuple[dict[str, Any], ...]
