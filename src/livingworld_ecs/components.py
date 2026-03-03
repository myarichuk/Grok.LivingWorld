"""Example components for ECS entities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    x: float
    y: float


@dataclass(frozen=True)
class Health:
    current: int
    maximum: int
