"""Morale, emotion, relationship-memory, and status-effect hooks for the engine."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ecs.core import EntityId, EntityQuery, SystemResult, World
from ttrpg_engine.components.actor import CurrentAction, ScenePosition, ScenePresence
from ttrpg_engine.components.emotional import EmotionalState
from ttrpg_engine.components.kernel import KernelState
from ttrpg_engine.components.memory import ActorMemory
from ttrpg_engine.components.relationship import (
    RelationshipMemory,
    RelationshipMemoryLink,
)
from ttrpg_engine.components.status import StatusEffect, StatusEffectTarget
from ttrpg_engine.events import (
    EmotionalStateChangedEvent,
    RelationshipMemoryUpdatedEvent,
    StatusEffectAppliedEvent,
    StatusEffectExpiredEvent,
)


class MoraleSystem:
    """Advance morale/stress toward equilibrium and enforce threshold consequences."""

    name: str = "morale_system"
    query: EntityQuery = EntityQuery(all_of=(KernelState,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Tick emotional equilibrium once per kernel turn."""
        if not entities:
            return SystemResult(self.name, 0, {"processed": [], "thresholds": []})

        turn_id = world.get_component(entities[0], KernelState).turn_id
        processed: list[dict[str, object]] = []
        thresholds: list[dict[str, object]] = []

        for actor_entity in world.query(EntityQuery(all_of=(EmotionalState,))):
            state = world.get_component(actor_entity, EmotionalState)
            next_state = replace(
                state,
                morale=_move_toward(state.morale, 50, step=1),
                stress=_move_toward(state.stress, 0, step=1),
            )
            if next_state != state:
                world.add_component(actor_entity, next_state)
                processed.append(
                    {
                        "actor_entity_id": actor_entity,
                        "morale": next_state.morale,
                        "stress": next_state.stress,
                    }
                )
                world.publish(
                    EmotionalStateChangedEvent(
                        actor_entity_id=actor_entity,
                        morale=next_state.morale,
                        stress=next_state.stress,
                        dominant_emotion=next_state.dominant_emotion,
                        reason="natural_decay",
                        turn_id=turn_id,
                        source=self.name,
                    )
                )

            threshold_updates = _apply_morale_threshold_effects(
                world=world,
                actor_entity=actor_entity,
                state=next_state,
                turn_id=turn_id,
                source=self.name,
            )
            thresholds.extend(threshold_updates)

            _compact_short_term_memory(world, actor_entity, turn_id)

        return SystemResult(
            self.name,
            len(entities),
            {"processed": processed, "thresholds": thresholds},
        )


class StatusEffectSystem:
    """Expire temporary status effects and publish lifecycle events."""

    name: str = "status_effect_system"
    query: EntityQuery = EntityQuery(all_of=(KernelState,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        if not entities:
            return SystemResult(self.name, 0, {"expired": []})

        turn_id = world.get_component(entities[0], KernelState).turn_id
        expired: list[dict[str, object]] = []
        effect_entities = world.query(EntityQuery(all_of=(StatusEffect, StatusEffectTarget)))

        for effect_entity in effect_entities:
            effect = world.get_component(effect_entity, StatusEffect)
            target = world.get_component(effect_entity, StatusEffectTarget)
            if effect.expires_turn is None or effect.expires_turn > turn_id:
                continue
            world.publish(
                StatusEffectExpiredEvent(
                    actor_entity_id=target.actor_entity_id,
                    effect_name=effect.name,
                    turn_id=turn_id,
                    source=self.name,
                )
            )
            world.destroy_entity(effect_entity)
            expired.append(
                {
                    "effect_entity": effect_entity,
                    "actor_entity_id": target.actor_entity_id,
                    "effect_name": effect.name,
                }
            )

        return SystemResult(self.name, len(entities), {"expired": expired})


def apply_emotional_change(
    world: World,
    actor_id: int,
    morale_delta: int = 0,
    stress_delta: int = 0,
    affection_delta: int | dict[int, int] | None = None,
    fear_delta: int | dict[int, int] | None = None,
    anger_delta: int | dict[int, int] | None = None,
    trust_delta: int | dict[int, int] | None = None,
    loyalty_delta: int | dict[int, int] | None = None,
    reason: str = "",
) -> EmotionalState:
    """Apply direct emotional deltas to an actor.

    Scalar directed-emotion deltas are tracked against the actor's own entity id so
    the LLM can call a simple hook without constructing per-target maps.
    """
    state = get_emotional_state(world, actor_id)
    next_state = replace(
        state,
        morale=_clamp_0_100(state.morale + morale_delta),
        stress=_clamp_0_100(state.stress + stress_delta),
        affection=_apply_directed_delta_map(
            state.affection, actor_id, affection_delta, min_value=-100, max_value=100
        ),
        fear=_apply_directed_delta_map(
            state.fear, actor_id, fear_delta, min_value=-100, max_value=100
        ),
        anger=_apply_directed_delta_map(
            state.anger, actor_id, anger_delta, min_value=-100, max_value=100
        ),
        trust=_apply_directed_delta_map(
            state.trust, actor_id, trust_delta, min_value=-100, max_value=100
        ),
        loyalty=_apply_directed_delta_map(
            state.loyalty, actor_id, loyalty_delta, min_value=-100, max_value=100
        ),
        dominant_emotion=_resolve_dominant_emotion(
            state=state,
            affection_delta=affection_delta,
            fear_delta=fear_delta,
            anger_delta=anger_delta,
            trust_delta=trust_delta,
            loyalty_delta=loyalty_delta,
        ),
    )
    world.add_component(actor_id, next_state)
    _append_actor_memory(
        world=world,
        actor_id=actor_id,
        memory={
            "turn": _current_turn(world),
            "kind": "emotional_change",
            "description": reason.strip() or "emotional state shifted",
            "morale_delta": morale_delta,
            "stress_delta": stress_delta,
        },
    )
    world.publish(
        EmotionalStateChangedEvent(
            actor_entity_id=actor_id,
            morale=next_state.morale,
            stress=next_state.stress,
            dominant_emotion=next_state.dominant_emotion,
            reason=reason.strip(),
            turn_id=_current_turn(world),
            source="apply_emotional_change",
        )
    )
    _apply_morale_threshold_effects(
        world=world,
        actor_entity=actor_id,
        state=next_state,
        turn_id=_current_turn(world),
        source="apply_emotional_change",
    )
    return next_state


def apply_relationship_change(
    world: World,
    source_id: int,
    target_id: int,
    trust_delta: int = 0,
    affection_delta: int = 0,
    fear_delta: int = 0,
    reason: str = "",
) -> RelationshipMemory:
    """Apply directed relationship changes and synchronize emotional overlays."""
    relationship_entity = _get_or_create_relationship_memory_entity(
        world=world,
        source_id=source_id,
        target_id=target_id,
    )
    memory = world.get_component(relationship_entity, RelationshipMemory)
    resentment_delta = 0
    if trust_delta < 0 or affection_delta < 0:
        resentment_delta = abs(min(trust_delta, 0)) + abs(min(affection_delta, 0))

    next_memory = replace(
        memory,
        trust=_clamp_signed(memory.trust + trust_delta),
        affection=_clamp_signed(memory.affection + affection_delta),
        fear=_clamp_signed(memory.fear + fear_delta),
        resentment=_clamp_signed(memory.resentment + resentment_delta),
        key_events=memory.key_events
        + (
            {
                "turn": _current_turn(world),
                "description": reason.strip() or "relationship shifted",
                "emotional_impact": {
                    "trust_delta": trust_delta,
                    "affection_delta": affection_delta,
                    "fear_delta": fear_delta,
                    "resentment_delta": resentment_delta,
                },
            },
        ),
        last_meaningful_interaction_turn=_current_turn(world),
    )
    world.add_component(relationship_entity, next_memory)
    apply_emotional_change(
        world=world,
        actor_id=source_id,
        trust_delta={target_id: trust_delta},
        affection_delta={target_id: affection_delta},
        fear_delta={target_id: fear_delta},
        reason=reason,
    )
    world.publish(
        RelationshipMemoryUpdatedEvent(
            source_actor_entity_id=source_id,
            target_actor_entity_id=target_id,
            trust=next_memory.trust,
            affection=next_memory.affection,
            fear=next_memory.fear,
            resentment=next_memory.resentment,
            turn_id=_current_turn(world),
            reason=reason.strip(),
            source="apply_relationship_change",
        )
    )
    return next_memory


def get_emotional_state(world: World, actor_id: int) -> EmotionalState:
    """Return an actor emotional state, creating a default state when absent."""
    if world.has_component(actor_id, EmotionalState):
        return world.get_component(actor_id, EmotionalState)
    state = EmotionalState()
    world.add_component(actor_id, state)
    return state


def get_morale(world: World, actor_id: int) -> int:
    """Return the current morale score for an actor."""
    return get_emotional_state(world, actor_id).morale


def get_relationship_memory(
    world: World, source_id: int, target_id: int
) -> RelationshipMemory | None:
    """Return a directed relationship memory for a source/target pair."""
    entity = _find_relationship_memory_entity(world, source_id, target_id)
    if entity is None:
        return None
    return world.get_component(entity, RelationshipMemory)


def get_actor_emotional_summary(world: World, actor_id: int) -> dict[str, object]:
    """Return rich emotional state, relationship overlays, and statuses for an actor."""
    emotional_state = get_emotional_state(world, actor_id)
    statuses = _status_effect_summaries(world, actor_id)
    relationships = tuple(
        {
            "target_actor_entity_id": link.target_actor_entity_id,
            "trust": memory.trust,
            "affection": memory.affection,
            "fear": memory.fear,
            "resentment": memory.resentment,
            "last_meaningful_interaction_turn": memory.last_meaningful_interaction_turn,
        }
        for link, memory in _relationship_memories_for_source(world, actor_id)
    )
    return {
        "actor_entity_id": actor_id,
        "emotional_state": emotional_state.emotional_summary(),
        "statuses": statuses,
        "relationships": relationships,
    }


def get_actor_full_summary(world: World, actor_id: int) -> dict[str, object]:
    """Return a rich summary for prompting, inspection, and memory retrieval."""
    emotional = get_actor_emotional_summary(world, actor_id)
    actor_memory = _get_actor_memory(world, actor_id)
    scene_id = ""
    zone = ""
    distance_bucket = ""
    if world.has_component(actor_id, ScenePresence):
        scene_id = world.get_component(actor_id, ScenePresence).scene_id
    if world.has_component(actor_id, ScenePosition):
        position = world.get_component(actor_id, ScenePosition)
        zone = position.zone
        distance_bucket = position.distance_bucket.value
    current_action = ""
    if world.has_component(actor_id, CurrentAction):
        current_action = world.get_component(actor_id, CurrentAction).description

    return {
        "actor_entity_id": actor_id,
        "current_action": current_action,
        "scene_id": scene_id,
        "zone": zone,
        "distance_bucket": distance_bucket,
        "emotional": emotional,
        "memory": {
            "short_term_memories": actor_memory.short_term_memories,
            "long_term_memories": actor_memory.long_term_memories,
            "beliefs_about": actor_memory.beliefs_about,
            "known_secrets": actor_memory.known_secrets,
        },
    }


def _apply_morale_threshold_effects(
    world: World,
    actor_entity: int,
    state: EmotionalState,
    turn_id: int,
    source: str,
) -> list[dict[str, object]]:
    updates: list[dict[str, object]] = []
    if state.morale <= 20:
        if _ensure_status_effect(
            world=world,
            actor_entity=actor_entity,
            name="broken",
            source=source,
            magnitude=-20,
            applied_turn=turn_id,
            tags=("morale", "threshold"),
        ):
            updates.append({"actor_entity_id": actor_entity, "effect": "broken"})
    else:
        _remove_status_effect(world, actor_entity, "broken")

    if state.morale >= 80:
        if _ensure_status_effect(
            world=world,
            actor_entity=actor_entity,
            name="inspired",
            source=source,
            magnitude=10,
            applied_turn=turn_id,
            tags=("morale", "threshold"),
        ):
            updates.append({"actor_entity_id": actor_entity, "effect": "inspired"})
    else:
        _remove_status_effect(world, actor_entity, "inspired")

    if state.stress >= 80:
        if _ensure_status_effect(
            world=world,
            actor_entity=actor_entity,
            name="rattled",
            source=source,
            magnitude=-10,
            applied_turn=turn_id,
            tags=("stress", "threshold"),
        ):
            updates.append({"actor_entity_id": actor_entity, "effect": "rattled"})
    else:
        _remove_status_effect(world, actor_entity, "rattled")

    return updates


def _ensure_status_effect(
    world: World,
    actor_entity: int,
    name: str,
    source: str,
    magnitude: int,
    applied_turn: int,
    tags: tuple[str, ...],
) -> bool:
    existing = _find_status_effect_entity(world, actor_entity, name)
    if existing is not None:
        effect = world.get_component(existing, StatusEffect)
        world.add_component(
            existing,
            replace(
                effect,
                source=source,
                magnitude=magnitude,
                applied_turn=applied_turn,
                tags=tags,
            ),
        )
        return False

    effect_entity = world.create_entity()
    world.add_component(effect_entity, StatusEffectTarget(actor_entity_id=actor_entity))
    world.add_component(
        effect_entity,
        StatusEffect(
            name=name,
            source=source,
            magnitude=magnitude,
            applied_turn=applied_turn,
            tags=tags,
        ),
    )
    world.publish(
        StatusEffectAppliedEvent(
            actor_entity_id=actor_entity,
            effect_name=name,
            magnitude=magnitude,
            turn_id=applied_turn,
            source=source,
        )
    )
    return True


def _remove_status_effect(world: World, actor_entity: int, name: str) -> None:
    entity = _find_status_effect_entity(world, actor_entity, name)
    if entity is None:
        return
    world.destroy_entity(entity)


def _find_status_effect_entity(
    world: World, actor_entity: int, name: str
) -> int | None:
    for entity in world.query(EntityQuery(all_of=(StatusEffect, StatusEffectTarget))):
        effect = world.get_component(entity, StatusEffect)
        target = world.get_component(entity, StatusEffectTarget)
        if target.actor_entity_id == actor_entity and effect.name == name:
            return entity
    return None


def _status_effect_summaries(world: World, actor_entity: int) -> tuple[dict[str, object], ...]:
    summaries: list[dict[str, object]] = []
    for entity in world.query(EntityQuery(all_of=(StatusEffect, StatusEffectTarget))):
        effect = world.get_component(entity, StatusEffect)
        target = world.get_component(entity, StatusEffectTarget)
        if target.actor_entity_id != actor_entity:
            continue
        summaries.append(
            {
                "name": effect.name,
                "magnitude": effect.magnitude,
                "applied_turn": effect.applied_turn,
                "expires_turn": effect.expires_turn,
                "tags": effect.tags,
            }
        )
    return tuple(sorted(summaries, key=lambda item: str(item["name"])))


def _get_or_create_relationship_memory_entity(
    world: World, source_id: int, target_id: int
) -> int:
    existing = _find_relationship_memory_entity(world, source_id, target_id)
    if existing is not None:
        return existing
    entity = world.create_entity()
    world.add_component(
        entity,
        RelationshipMemoryLink(
            source_actor_entity_id=source_id,
            target_actor_entity_id=target_id,
        ),
    )
    world.add_component(entity, RelationshipMemory())
    return entity


def _find_relationship_memory_entity(
    world: World, source_id: int, target_id: int
) -> int | None:
    for entity in world.query(EntityQuery(all_of=(RelationshipMemory, RelationshipMemoryLink))):
        link = world.get_component(entity, RelationshipMemoryLink)
        if (
            link.source_actor_entity_id == source_id
            and link.target_actor_entity_id == target_id
        ):
            return entity
    return None


def _relationship_memories_for_source(
    world: World, actor_id: int
) -> tuple[tuple[RelationshipMemoryLink, RelationshipMemory], ...]:
    memories: list[tuple[RelationshipMemoryLink, RelationshipMemory]] = []
    for entity in world.query(EntityQuery(all_of=(RelationshipMemory, RelationshipMemoryLink))):
        link = world.get_component(entity, RelationshipMemoryLink)
        if link.source_actor_entity_id != actor_id:
            continue
        memories.append((link, world.get_component(entity, RelationshipMemory)))
    memories.sort(key=lambda item: item[0].target_actor_entity_id)
    return tuple(memories)


def _get_actor_memory(world: World, actor_id: int) -> ActorMemory:
    if world.has_component(actor_id, ActorMemory):
        return world.get_component(actor_id, ActorMemory)
    memory = ActorMemory()
    world.add_component(actor_id, memory)
    return memory


def _append_actor_memory(
    world: World, actor_id: int, memory: dict[str, Any], short_term_limit: int = 8
) -> None:
    actor_memory = _get_actor_memory(world, actor_id)
    short_term = actor_memory.short_term_memories + (dict(memory),)
    if len(short_term) > short_term_limit:
        promoted = short_term[0]
        short_term = short_term[1:]
        long_term = actor_memory.long_term_memories + (promoted,)
    else:
        long_term = actor_memory.long_term_memories

    world.add_component(
        actor_id,
        replace(
            actor_memory,
            short_term_memories=short_term,
            long_term_memories=long_term,
        ),
    )


def _compact_short_term_memory(world: World, actor_id: int, turn_id: int) -> None:
    actor_memory = _get_actor_memory(world, actor_id)
    if len(actor_memory.short_term_memories) <= 8:
        return
    promoted = actor_memory.short_term_memories[0]
    updated_promoted = dict(promoted)
    updated_promoted.setdefault("promoted_turn", turn_id)
    world.add_component(
        actor_id,
        replace(
            actor_memory,
            short_term_memories=actor_memory.short_term_memories[1:],
            long_term_memories=actor_memory.long_term_memories + (updated_promoted,),
        ),
    )


def _apply_directed_delta_map(
    values: dict[int, int],
    actor_id: int,
    delta: int | dict[int, int] | None,
    min_value: int,
    max_value: int,
) -> dict[int, int]:
    next_values = dict(values)
    if delta is None:
        return next_values
    if isinstance(delta, int):
        if delta == 0:
            return next_values
        next_values[actor_id] = _clamp(next_values.get(actor_id, 0) + delta, min_value, max_value)
        return next_values
    for target_id, change in delta.items():
        next_values[int(target_id)] = _clamp(
            next_values.get(int(target_id), 0) + int(change),
            min_value,
            max_value,
        )
    return next_values


def _resolve_dominant_emotion(
    state: EmotionalState,
    affection_delta: int | dict[int, int] | None,
    fear_delta: int | dict[int, int] | None,
    anger_delta: int | dict[int, int] | None,
    trust_delta: int | dict[int, int] | None,
    loyalty_delta: int | dict[int, int] | None,
) -> str:
    candidates = {
        "affection": _delta_strength(affection_delta),
        "fear": _delta_strength(fear_delta),
        "anger": _delta_strength(anger_delta),
        "trust": _delta_strength(trust_delta),
        "loyalty": _delta_strength(loyalty_delta),
    }
    emotion, strength = max(candidates.items(), key=lambda item: item[1])
    if strength <= 0:
        return state.dominant_emotion
    return emotion


def _delta_strength(delta: int | dict[int, int] | None) -> int:
    if delta is None:
        return 0
    if isinstance(delta, int):
        return abs(delta)
    return max((abs(int(value)) for value in delta.values()), default=0)


def _current_turn(world: World) -> int:
    kernels = world.query(EntityQuery(all_of=(KernelState,)))
    if not kernels:
        return -1
    return world.get_component(kernels[0], KernelState).turn_id


def _move_toward(value: int, target: int, step: int) -> int:
    if value < target:
        return min(target, value + step)
    if value > target:
        return max(target, value - step)
    return value


def _clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


def _clamp_0_100(value: int) -> int:
    return _clamp(value, 0, 100)


def _clamp_signed(value: int) -> int:
    return _clamp(value, -100, 100)


EXAMPLE_USAGE = """
Example:
    from ecs import World
    from ttrpg_engine.components.emotional import EmotionalState
    from ttrpg_engine.morale_system import (
        MoraleSystem,
        apply_emotional_change,
        apply_relationship_change,
        get_actor_full_summary,
    )

    world = World(enable_storage=False)
    actor = world.create_entity()
    world.add_component(actor, EmotionalState())

    apply_emotional_change(
        world,
        actor,
        morale_delta=-25,
        fear_delta=15,
        reason="Player betrayed her",
    )
    apply_relationship_change(world, actor, 99, trust_delta=-30, reason="Broken oath")
    summary = get_actor_full_summary(world, actor)
    MoraleSystem().run(world, [])
"""
