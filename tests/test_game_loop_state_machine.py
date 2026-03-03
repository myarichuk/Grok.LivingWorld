from __future__ import annotations

from ecs.core import World
from ttrpg_engine.components import (
    EndTurnCommand,
    KernelState,
    LLMResponse,
    NeedsLLMFill,
    RequestRegistry,
    StartTurnCommand,
    TurnPhase,
)
from ttrpg_engine.systems import (
    ApplyLLMResponseSystem,
    CommitTurnSystem,
    EndTurnSystem,
    StartTurnSystem,
)


def _kernel_entity(world: World) -> int:
    entity = world.create_entity()
    world.add_component(entity, KernelState())
    world.add_component(entity, RequestRegistry())
    return entity


def test_state_machine_happy_path_from_idle_to_committed_and_back_to_idle() -> None:
    world = World()
    kernel = _kernel_entity(world)

    world.add_component(
        kernel,
        StartTurnCommand(
            request_type="generate_location",
            context={"biome": "swamp"},
            schema={"required": ["name", "description"]},
            advance_minutes=15,
        ),
    )

    start_result = StartTurnSystem().run(world, [kernel])
    request_id = start_result.payload["started"][0]["request_id"]

    state = world.get_component(kernel, KernelState)
    registry = world.get_component(kernel, RequestRegistry)
    request_entities = world.query_entities((NeedsLLMFill,))

    assert state.phase == TurnPhase.WAITING_FOR_LLM
    assert state.turn_id == 1
    assert registry.pending_request_ids == (request_id,)
    assert len(request_entities) == 1

    world.add_component(
        kernel,
        LLMResponse(
            request_id=request_id,
            payload={"name": "Mirewatch", "description": "Fog-choked boardwalks."},
        ),
    )

    apply_result = ApplyLLMResponseSystem().run(world, [kernel])

    assert apply_result.payload["rejected"] == []
    assert apply_result.payload["applied"][0]["request_id"] == request_id
    assert world.get_component(kernel, KernelState).phase == TurnPhase.RESOLVING
    assert world.get_component(kernel, RequestRegistry).pending_request_ids == ()
    assert (
        world.get_component(kernel, RequestRegistry).applied_request_ids
        == (request_id,)
    )

    CommitTurnSystem().run(world, [kernel])
    committed_state = world.get_component(kernel, KernelState)
    assert committed_state.phase == TurnPhase.COMMITTED
    assert committed_state.time_minutes == 15

    world.add_component(kernel, EndTurnCommand())
    end_result = EndTurnSystem().run(world, [kernel])

    assert end_result.payload["ended"] == [kernel]
    assert world.get_component(kernel, KernelState).phase == TurnPhase.IDLE


def test_apply_llm_response_rejects_unknown_and_duplicate_request_ids() -> None:
    world = World()
    kernel = _kernel_entity(world)

    world.add_component(
        kernel,
        StartTurnCommand(
            request_type="generate_inventory",
            schema={"required": ["items"]},
        ),
    )
    start_result = StartTurnSystem().run(world, [kernel])
    request_id = start_result.payload["started"][0]["request_id"]

    world.add_component(
        kernel,
        LLMResponse(request_id="unknown", payload={"items": []}),
    )
    unknown_result = ApplyLLMResponseSystem().run(world, [kernel])
    assert unknown_result.payload["rejected"][0]["reason"] == "unknown request_id"

    world.add_component(
        kernel,
        LLMResponse(request_id=request_id, payload={"items": []}),
    )
    first_apply = ApplyLLMResponseSystem().run(world, [kernel])
    assert first_apply.payload["applied"][0]["request_id"] == request_id

    world.add_component(
        kernel,
        LLMResponse(request_id=request_id, payload={"items": []}),
    )
    duplicate_result = ApplyLLMResponseSystem().run(world, [kernel])
    assert (
        duplicate_result.payload["rejected"][0]["reason"]
        == "request already applied"
    )


def test_apply_llm_response_enforces_required_schema_keys() -> None:
    world = World()
    kernel = _kernel_entity(world)

    world.add_component(
        kernel,
        StartTurnCommand(
            request_type="batch_agendas",
            schema={"required": ["agendas", "window_minutes"]},
        ),
    )
    start_result = StartTurnSystem().run(world, [kernel])
    request_id = start_result.payload["started"][0]["request_id"]

    world.add_component(
        kernel,
        LLMResponse(request_id=request_id, payload={"agendas": []}),
    )
    apply_result = ApplyLLMResponseSystem().run(world, [kernel])

    assert "window_minutes" in apply_result.payload["rejected"][0]["reason"]
    assert (
        world.get_component(kernel, RequestRegistry).pending_request_ids
        == (request_id,)
    )
    assert world.get_component(kernel, KernelState).phase == TurnPhase.WAITING_FOR_LLM
