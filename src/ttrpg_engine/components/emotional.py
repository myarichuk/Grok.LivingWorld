"""Emotional-state components for long-form NPC and player arcs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmotionalState:
    """Actor emotional state with coarse morale/stress and directed feelings."""

    morale: int = 50
    stress: int = 0
    dominant_emotion: str = "steady"
    affection: dict[int, int] = field(default_factory=dict)
    fear: dict[int, int] = field(default_factory=dict)
    anger: dict[int, int] = field(default_factory=dict)
    trust: dict[int, int] = field(default_factory=dict)
    loyalty: dict[int, int] = field(default_factory=dict)

    def emotional_summary(self) -> dict[str, object]:
        """Return a compact emotional summary for prompting and inspection."""
        return {
            "morale": self.morale,
            "stress": self.stress,
            "dominant_emotion": self.dominant_emotion,
            "top_affection": _top_feelings(self.affection),
            "top_fear": _top_feelings(self.fear),
            "top_anger": _top_feelings(self.anger),
            "top_trust": _top_feelings(self.trust),
            "top_loyalty": _top_feelings(self.loyalty),
        }


def _top_feelings(values: dict[int, int], limit: int = 3) -> tuple[dict[str, int], ...]:
    ranked = sorted(values.items(), key=lambda item: (-abs(item[1]), item[0]))
    return tuple(
        {"actor_entity_id": actor_entity_id, "value": value}
        for actor_entity_id, value in ranked[: max(0, limit)]
    )


EXAMPLE_USAGE = """
Example:
    from ecs import World
    from ttrpg_engine.components.emotional import EmotionalState

    world = World(enable_storage=False)
    actor = world.create_entity()
    world.add_component(actor, EmotionalState(morale=60, stress=15))
"""
