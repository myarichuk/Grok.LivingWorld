"""Status-effect components for morale, stress, and narrative conditions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StatusEffect:
    """A temporary or persistent status modifier."""

    name: str
    source: str
    magnitude: int = 0
    applied_turn: int = -1
    expires_turn: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StatusEffectTarget:
    """Links a status effect entity to its target actor."""

    actor_entity_id: int


EXAMPLE_USAGE = """
Example:
    from ecs import World
    from ttrpg_engine.components.status import StatusEffect, StatusEffectTarget

    world = World(enable_storage=False)
    effect = world.create_entity()
    world.add_component(effect, StatusEffectTarget(actor_entity_id=12))
    world.add_component(effect, StatusEffect(name="broken", source="morale_system"))
"""
