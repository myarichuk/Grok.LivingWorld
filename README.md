# ECS + TTRPG Engine

Generic ECS primitives separated from TTRPG domain implementations.

## Structure

- `src/ecs/` - generic ECS core (`World`, `GlobalSystem`, `SystemResult`).
- `src/ttrpg_engine/` - deterministic game-loop state machine and LLM request flow.
- `src/ttrpg_5e/` - D&D 5e actor components plus actor factory abstraction.
- `tests/` - unit tests for ECS core, 5e factory, and state machine behavior.

## Quick start

```python
from ecs import World
from ttrpg_engine import (
    ApplyLLMResponseSystem,
    CommitTurnSystem,
    KernelState,
    LLMResponse,
    RequestRegistry,
    StartTurnCommand,
    StartTurnSystem,
)

world = World()
kernel = world.create_entity()
world.add_component(kernel, KernelState())
world.add_component(kernel, RequestRegistry())
world.add_component(
    kernel,
    StartTurnCommand(
        request_type="generate_location",
        schema={"required": ["name", "description"]},
    ),
)

start_result = StartTurnSystem().run(world, [kernel])
request_id = start_result.payload["started"][0]["request_id"]

world.add_component(
    kernel,
    LLMResponse(
        request_id=request_id,
        payload={"name": "The Salty Wench", "description": "A storm-battered inn."},
    ),
)

ApplyLLMResponseSystem().run(world, [kernel])
CommitTurnSystem().run(world, [kernel])
```

## Development checks

```bash
ruff check .
pytest
```
