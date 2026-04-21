"""Actor memory components for short-term, long-term, and belief tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActorMemory:
    """Narrative memory buckets owned by an actor."""

    short_term_memories: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    long_term_memories: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    beliefs_about: dict[int, dict[str, Any]] = field(default_factory=dict)
    known_secrets: tuple[str, ...] = field(default_factory=tuple)


EXAMPLE_USAGE = """
Example:
    from ecs import World
    from ttrpg_engine.components.memory import ActorMemory

    world = World(enable_storage=False)
    actor = world.create_entity()
    world.add_component(
        actor,
        ActorMemory(
            short_term_memories=(
                {"turn": 4, "description": "The captain lied to me."},
            ),
        ),
    )
"""
