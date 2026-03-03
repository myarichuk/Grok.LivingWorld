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
    actor_name: str
    scene_id: str
    long_term_goals: tuple[str, ...]
    faction_relations: dict[str, int]
    possible_goals: tuple[str, ...] = ()
    actor_entity_id: int | None = None
    actor_kind: str = "llm_npc"
    suggested_impulse: str = ""
