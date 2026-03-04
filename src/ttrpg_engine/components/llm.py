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
