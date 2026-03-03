from __future__ import annotations

from ecs.core import World
from ttrpg_engine.components import (
    ActorAgency,
    FactionRelations,
    KernelState,
    LLMActorRegistrationCommand,
    LongTermGoals,
    NarrativeActor,
    TurnPhase,
)
from ttrpg_engine.events import ActorImpulseEvent, ActorRegisteredEvent
from ttrpg_engine.systems import LLMActorGatewaySystem


def test_llm_actor_gateway_registers_actor_and_publishes_events() -> None:
    world = World()

    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=12, current_location="dock"),
    )

    command_entity = world.create_entity()
    world.add_component(
        command_entity,
        LLMActorRegistrationCommand(
            actor_name="Kestrel",
            scene_id="dock",
            long_term_goals=("secure smuggling route", "build local network"),
            faction_relations={"city_watch": -25, "dock_union": 150},
        ),
    )

    registered_events: list[ActorRegisteredEvent] = []
    impulse_events: list[ActorImpulseEvent] = []
    world.subscribe(ActorRegisteredEvent, registered_events.append)
    world.subscribe(ActorImpulseEvent, impulse_events.append)

    result = LLMActorGatewaySystem().run(world, [command_entity])

    registered_actor = result.payload["registered"][0]["actor_entity"]
    actor = world.get_component(registered_actor, NarrativeActor)
    goals = world.get_component(registered_actor, LongTermGoals)
    factions = world.get_component(registered_actor, FactionRelations)
    agency = world.get_component(registered_actor, ActorAgency)

    assert actor.name == "Kestrel"
    assert goals.goals[0] == "secure smuggling route"
    assert factions.standings == {"city_watch": -25, "dock_union": 100}
    assert agency.short_term_goal == "secure smuggling route"
    assert agency.impulse != ""
    assert agency.last_impulse_turn == 12

    assert len(registered_events) == 1
    assert registered_events[0].actor_entity_id == registered_actor
    assert len(impulse_events) == 1
    assert impulse_events[0].actor_entity_id == registered_actor


def test_world_pubsub_allows_external_api_actor_impulse_event() -> None:
    world = World()

    seen: list[ActorImpulseEvent] = []
    world.subscribe(ActorImpulseEvent, seen.append)

    external_event = ActorImpulseEvent(
        actor_entity_id=10,
        target_entity_id=11,
        scene_id="market",
        turn_id=5,
        impulse="shoves target and runs",
        source="external_api",
    )
    world.publish(external_event)

    assert seen == [external_event]
    queued = world.get_published_events(ActorImpulseEvent)
    assert queued == [external_event]

    consumed = world.consume_published_events(ActorImpulseEvent)
    assert consumed == [external_event]
    assert world.get_published_events(ActorImpulseEvent) == []
