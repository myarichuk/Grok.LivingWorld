from __future__ import annotations

from ecs.core import EntityQuery, World
from ttrpg_engine.components import (
    ActorMemory,
    CurrentAction,
    DistanceBucket,
    EmotionalState,
    KernelState,
    NarrativeActor,
    RelationshipMemory,
    ScenePosition,
    ScenePresence,
    StatusEffect,
    StatusEffectTarget,
    TurnPhase,
)
from ttrpg_engine.events import (
    EmotionalStateChangedEvent,
    RelationshipMemoryUpdatedEvent,
    StatusEffectAppliedEvent,
    StatusEffectExpiredEvent,
)
from ttrpg_engine.morale_system import (
    MoraleSystem,
    StatusEffectSystem,
    apply_emotional_change,
    apply_relationship_change,
    get_actor_emotional_summary,
    get_actor_full_summary,
    get_morale,
    get_relationship_memory,
)


def test_apply_emotional_change_updates_state_and_memory() -> None:
    world = World(enable_storage=False)
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=7, current_location="dock"),
    )
    actor = world.create_entity()

    events: list[EmotionalStateChangedEvent] = []
    world.subscribe(EmotionalStateChangedEvent, events.append)

    state = apply_emotional_change(
        world,
        actor,
        morale_delta=-25,
        stress_delta=10,
        fear_delta=15,
        reason="Player betrayed her",
    )

    assert state.morale == 25
    assert state.stress == 10
    assert state.dominant_emotion == "fear"
    assert state.fear[actor] == 15
    assert len(events) == 1
    memory = world.get_component(actor, ActorMemory)
    assert memory.short_term_memories[-1]["description"] == "Player betrayed her"


def test_apply_relationship_change_creates_relationship_memory_and_event() -> None:
    world = World(enable_storage=False)
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=9, current_location="market"),
    )
    source = world.create_entity()
    target = world.create_entity()

    events: list[RelationshipMemoryUpdatedEvent] = []
    world.subscribe(RelationshipMemoryUpdatedEvent, events.append)

    memory = apply_relationship_change(
        world,
        source,
        target,
        trust_delta=-30,
        affection_delta=-10,
        fear_delta=20,
        reason="Broken oath",
    )

    assert memory.trust == -30
    assert memory.affection == -10
    assert memory.fear == 20
    assert memory.resentment == 40
    assert memory.key_events[-1]["description"] == "Broken oath"
    assert len(events) == 1
    loaded = get_relationship_memory(world, source, target)
    assert loaded is not None
    assert loaded.last_meaningful_interaction_turn == 9


def test_morale_system_applies_threshold_status_effects() -> None:
    world = World(enable_storage=False)
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=12, current_location="camp"),
    )
    actor = world.create_entity()
    world.add_component(actor, EmotionalState(morale=15, stress=82))

    applied: list[StatusEffectAppliedEvent] = []
    world.subscribe(StatusEffectAppliedEvent, applied.append)

    result = MoraleSystem().run(world, [kernel])

    effect_names = {
        world.get_component(entity, StatusEffect).name
        for entity in world.query(EntityQuery(all_of=(StatusEffect, StatusEffectTarget)))
    }
    assert "broken" in effect_names
    assert "rattled" in effect_names
    assert result.payload["thresholds"]
    assert len(applied) >= 2


def test_status_effect_system_expires_elapsed_effects() -> None:
    world = World(enable_storage=False)
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=5, current_location="camp"),
    )
    actor = world.create_entity()
    effect = world.create_entity()
    world.add_component(effect, StatusEffectTarget(actor_entity_id=actor))
    world.add_component(
        effect,
        StatusEffect(
            name="inspired",
            source="test",
            applied_turn=1,
            expires_turn=5,
        ),
    )

    expired: list[StatusEffectExpiredEvent] = []
    world.subscribe(StatusEffectExpiredEvent, expired.append)
    result = StatusEffectSystem().run(world, [kernel])

    assert result.payload["expired"][0]["effect_name"] == "inspired"
    assert len(expired) == 1
    assert world.query(EntityQuery(all_of=(StatusEffect,))) == []


def test_actor_summaries_include_emotions_memory_location_and_action() -> None:
    world = World(enable_storage=False)
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=4, current_location="tavern"),
    )
    actor = world.create_entity()
    target = world.create_entity()
    world.add_component(actor, NarrativeActor(name="Kestrel"))
    world.add_component(actor, ScenePresence(scene_id="tavern"))
    world.add_component(
        actor,
        ScenePosition(
            scene_id="tavern",
            zone="bar",
            distance_bucket=DistanceBucket.NEAR,
        ),
    )
    world.add_component(
        actor,
        CurrentAction(description="watches the room", source="test", turn_id=4),
    )

    apply_emotional_change(world, actor, morale_delta=10, trust_delta={target: 25})
    apply_relationship_change(world, actor, target, trust_delta=25, reason="Shared a secret")

    emotional_summary = get_actor_emotional_summary(world, actor)
    full_summary = get_actor_full_summary(world, actor)

    assert emotional_summary["emotional_state"]["morale"] == 60
    assert emotional_summary["relationships"][0]["target_actor_entity_id"] == target
    assert get_morale(world, actor) == 60
    assert full_summary["current_action"] == "watches the room"
    assert full_summary["scene_id"] == "tavern"
    assert full_summary["memory"]["short_term_memories"]
