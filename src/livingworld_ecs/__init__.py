"""Public API for the lightweight LivingWorld ECS package."""

from livingworld_ecs.components import Health, Position
from livingworld_ecs.core import GlobalSystem, SystemResult, World
from livingworld_ecs.systems import HealthSummarySystem, SpatialSummarySystem

__all__ = [
    "GlobalSystem",
    "Health",
    "HealthSummarySystem",
    "Position",
    "SpatialSummarySystem",
    "SystemResult",
    "World",
]
