"""Kernel and turn-state components."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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
    pending_time_advance_minutes: int = field(default=0)


@dataclass(frozen=True)
class RequestRegistry:
    pending_request_ids: tuple[str, ...] = ()
    applied_request_ids: tuple[str, ...] = ()
