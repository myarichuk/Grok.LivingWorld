from __future__ import annotations

from dataclasses import replace

from ecs.core import EntityQuery, World
from ttrpg_5e.components import AbilityScores, Actor5e
from ttrpg_5e.factory import Actor5eFactory, ActorBuild5e
from ttrpg_engine.components import (
    ActorAgency,
    ActorImpulse,
    FactionRelations,
    KernelState,
    LLMActorRegistrationCommand,
    LLMResponse,
    LongTermGoals,
    NeedsLLMFill,
    RequestRegistry,
    ResolvedLLMResult,
    ScenePresence,
    StartTurnCommand,
    TurnPhase,
)
from ttrpg_engine.events import ActorImpulseEvent, ActorRegisteredEvent
from ttrpg_engine.systems import (
    ActorAgencySystem,
    ApplyLLMResponseSystem,
    LLMActorGatewaySystem,
    StartTurnSystem,
)


def _kernel_entity(world: World) -> int:
    entity = world.create_entity()
    world.add_component(
        entity,
        KernelState(phase=TurnPhase.IDLE, turn_id=0, current_location="dock"),
    )
    world.add_component(entity, RequestRegistry())
    return entity


def test_simulated_llm_turn_registers_actor_and_runs_agency() -> None:
    world = World()
    kernel = _kernel_entity(world)

    world.add_component(
        kernel,
        StartTurnCommand(
            request_type="register_actor",
            schema={
                "required": [
                    "actor_name",
                    "scene_id",
                    "long_term_goals",
                    "faction_relations",
                ]
            },
        ),
    )

    start_result = StartTurnSystem().run(world, [kernel])
    request_id = start_result.payload["started"][0]["request_id"]
    assert world.query(EntityQuery(all_of=(NeedsLLMFill,)))

    world.add_component(
        kernel,
        LLMResponse(
            request_id=request_id,
            payload={
                "actor_name": "Neris",
                "scene_id": "dock",
                "long_term_goals": ["secure food", "earn trust"],
                "faction_relations": {"dockers": 40, "guards": -10},
                "possible_goals": ["search for exits", "protect allies"],
            },
        ),
    )
    apply_result = ApplyLLMResponseSystem().run(world, [kernel])
    assert apply_result.payload["rejected"] == []

    resolved_entities = world.query(EntityQuery(all_of=(ResolvedLLMResult,)))
    assert len(resolved_entities) == 1
    resolved = world.get_component(resolved_entities[0], ResolvedLLMResult)

    command_entity = world.create_entity()
    world.add_component(
        command_entity,
        LLMActorRegistrationCommand(
            actor_name=str(resolved.payload["actor_name"]),
            scene_id=str(resolved.payload["scene_id"]),
            long_term_goals=tuple(resolved.payload["long_term_goals"]),
            faction_relations=dict(resolved.payload["faction_relations"]),
            possible_goals=tuple(resolved.payload["possible_goals"]),
        ),
    )

    gateway_result = LLMActorGatewaySystem().run(world, [command_entity])
    actor_id = gateway_result.payload["registered"][0]["actor_entity"]

    world.add_component(
        kernel,
        replace(
            world.get_component(kernel, KernelState),
            phase=TurnPhase.RESOLVING,
            current_location="dock",
        ),
    )
    agency_result = ActorAgencySystem().run(world, [kernel])

    agency = world.get_component(actor_id, ActorAgency)
    goals = world.get_component(actor_id, LongTermGoals)
    factions = world.get_component(actor_id, FactionRelations)

    assert goals.goals == ("secure food", "earn trust")
    assert factions.standings == {"dockers": 40, "guards": -10}
    assert agency.short_term_goal != ""
    assert agency.impulse != ""
    assert agency_result.payload["processed"][0]["selected_actor_ids"] == [actor_id]

    published_registered = world.get_published_events(ActorRegisteredEvent)
    published_impulses = world.get_published_events(ActorImpulseEvent)
    impulse_components = world.query(EntityQuery(all_of=(ActorImpulse,)))
    assert len(published_registered) == 1
    assert len(published_impulses) >= 1
    assert len(impulse_components) >= 1


def test_simulated_llm_updates_existing_5e_actor_with_gateway() -> None:
    world = World()

    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=5, current_location="dock"),
    )

    actor_component = Actor5eFactory().create_actor(
        ActorBuild5e(
            name="Aria",
            race="Human",
            class_name="Rogue",
            level=3,
            background="Criminal",
            alignment="Chaotic Good",
            max_hit_points=24,
            armor_class=15,
            speed=30,
            hit_dice="d8",
            ability_scores=AbilityScores(10, 16, 14, 12, 13, 8),
        )
    )
    actor_entity = world.create_entity()
    world.add_component(actor_entity, actor_component)
    world.add_component(actor_entity, ScenePresence("dock"))

    llm_command = world.create_entity()
    world.add_component(
        llm_command,
        LLMActorRegistrationCommand(
            actor_name="Aria",
            actor_entity_id=actor_entity,
            scene_id="dock",
            long_term_goals=("expand spy network",),
            faction_relations={"guild": 25, "watch": -5},
            suggested_impulse="signals allies from the shadows",
        ),
    )

    result = LLMActorGatewaySystem().run(world, [llm_command])
    assert result.payload["registered"][0]["actor_entity"] == actor_entity

    # Existing concrete 5e actor component is still present and queryable.
    assert world.get_component(actor_entity, Actor5e).name == "Aria"

    agency = world.get_component(actor_entity, ActorAgency)
    goals = world.get_component(actor_entity, LongTermGoals)
    assert goals.goals == ("expand spy network",)
    assert agency.impulse == "signals allies from the shadows"
    assert agency.last_impulse_turn == 5
