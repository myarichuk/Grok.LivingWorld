from __future__ import annotations

from ecs.core import EntityQuery, World
from ttrpg_engine.components import (
    KernelState,
    LLMResponse,
    NeedsLLMFill,
    RequestRegistry,
    ResolvedLLMResult,
    TurnPhase,
)
from ttrpg_engine.systems import ApplyLLMResponseSystem


def test_apply_llm_response_rejects_type_mismatch_against_schema() -> None:
    world = World(enable_storage=False)
    kernel = world.create_entity()
    world.add_component(kernel, KernelState(phase=TurnPhase.WAITING_FOR_LLM, turn_id=1))
    world.add_component(kernel, RequestRegistry(pending_request_ids=("r1",)))

    request_entity = world.create_entity()
    world.add_component(
        request_entity,
        NeedsLLMFill(
            request_id="r1",
            turn_id=1,
            request_type="generate_location",
            context={},
            schema={
                "required": ["name"],
                "properties": {"name": {"type": "string"}},
                "additionalProperties": False,
            },
            schema_version="1.0",
        ),
    )

    world.add_component(kernel, LLMResponse(request_id="r1", payload={"name": 123}))
    result = ApplyLLMResponseSystem().run(world, [kernel])

    assert result.payload["applied"] == []
    assert result.payload["rejected"]
    assert not world.has_component(kernel, LLMResponse)
    assert world.query(EntityQuery(all_of=(ResolvedLLMResult,))) == []

