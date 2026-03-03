"""Game-loop components for a deterministic TTRPG kernel."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TurnPhase(str, Enum):
    IDLE = "IDLE"
    WAITING_FOR_LLM = "WAITING_FOR_LLM"
    RESOLVING = "RESOLVING"
    COMMITTED = "COMMITTED"


@dataclass(frozen=True)
class KernelState:
    phase: TurnPhase = TurnPhase.IDLE
    turn_id: int = 0
    time_minutes: int = 0
    current_location: str = ""
    last_interrupt_time: int = 0
    tension_cooldown: int = 30
    rng_seed: int = 1337
    rng_draws: int = 0
    pending_time_advance_minutes: int = 0


@dataclass(frozen=True)
class RequestRegistry:
    pending_request_ids: tuple[str, ...] = ()
    applied_request_ids: tuple[str, ...] = ()


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
