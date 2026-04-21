from __future__ import annotations

from ecs.core import EntityQuery, World
from ttrpg_engine.components import (
    Faction,
    KernelState,
    LLMActorRegistrationCommand,
    LLMFactionUpdateCommand,
    Location,
    NeedsLLMFill,
    RequestRegistry,
    StartTurnCommand,
    TurnPhase,
)
from ttrpg_engine.systems import LLMActorGatewaySystem, LLMFactionGatewaySystem, StartTurnSystem


def test_start_turn_rejects_blank_request_type() -> None:
    world = World(enable_storage=False)
    kernel = world.create_entity()
    world.add_component(kernel, KernelState(phase=TurnPhase.IDLE, turn_id=0))
    world.add_component(kernel, RequestRegistry())
    world.add_component(kernel, StartTurnCommand(request_type="   "))

    result = StartTurnSystem().run(world, [kernel])

    assert result.payload["started"] == []
    assert result.payload["rejected"]
    assert not world.has_component(kernel, StartTurnCommand)
    assert world.query(EntityQuery(all_of=(NeedsLLMFill,))) == []


def test_llm_actor_gateway_rejects_blank_scene_id() -> None:
    world = World(enable_storage=False)
    kernel = world.create_entity()
    world.add_component(
        kernel, KernelState(phase=TurnPhase.RESOLVING, turn_id=1, current_location="dock")
    )

    cmd_entity = world.create_entity()
    world.add_component(
        cmd_entity,
        LLMActorRegistrationCommand(
            actor_name="Kestrel",
            scene_id="   ",
            long_term_goals=(),
            faction_relations={},
        ),
    )

    result = LLMActorGatewaySystem().run(world, [cmd_entity])
    assert result.payload["registered"] == []
    assert result.payload["rejected"]
    assert not world.has_component(cmd_entity, LLMActorRegistrationCommand)
    assert world.query(EntityQuery(all_of=(Location,))) == []


def test_llm_faction_gateway_rejects_blank_faction_name() -> None:
    world = World(enable_storage=False)
    cmd_entity = world.create_entity()
    world.add_component(
        cmd_entity,
        LLMFactionUpdateCommand(faction_name="   "),
    )

    result = LLMFactionGatewaySystem().run(world, [cmd_entity])
    assert result.payload["updated"] == []
    assert result.payload["rejected"]
    assert not world.has_component(cmd_entity, LLMFactionUpdateCommand)
    assert world.query(EntityQuery(all_of=(Faction,))) == []

