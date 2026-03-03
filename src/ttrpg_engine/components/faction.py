"""Faction-related components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Faction:
    name: str


@dataclass(frozen=True)
class FactionHeat:
    value: int = 0


@dataclass(frozen=True)
class FactionFlags:
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class FactionGoals:
    global_goals: tuple[str, ...] = ()
    regional_goals: dict[str, tuple[str, ...]] | None = None


@dataclass(frozen=True)
class GrandPlanClock:
    name: str
    progress: float = 0.0
    max_progress: float = 100.0
    rate_per_turn: float = 1.0


@dataclass(frozen=True)
class FactionMembership:
    faction_entity_id: int
