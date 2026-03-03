# ECS + TTRPG Engine

Generic ECS primitives separated from TTRPG domain implementations.

## Structure

- `src/ecs/` - generic ECS core (`World`, `GlobalSystem`, `SystemResult`).
- `src/ttrpg_engine/` - deterministic game-loop state machine, actor agency, LLM gateway.
  - `components/kernel.py` - turn + kernel state
  - `components/llm.py` - LLM command/response components
  - `components/actor.py` - actor markers, agency, goals, faction relations
  - `events.py` - pub/sub event types
- `src/ttrpg_5e/` - D&D 5e actor components plus actor factory abstraction.
- `tests/` - unit tests for ECS core, 5e factory, and state machine behavior.

## ECS query style

The ECS core now uses query objects inspired by DefaultEcs:

```python
from ecs import EntityQuery

# has Health, does not have Hidden, and has at least one of Position/Token
query = EntityQuery(
    all_of=(Health,),
    none_of=(Hidden,),
    any_of=(Position, Token),
)
entities = world.query(query)
```

You can also use the fluent builder:

```python
query = (
    world.get_entities()
    .with_all(Health, Position)
    .without(Hidden)
    .with_any(Token, Marker)
    .as_query()
)
entity_set = world.create_entity_set(query)  # cached view
```

## Pub/sub broker

`World` also acts as an in-process broker:

```python
sub_id = world.subscribe(ActorImpulseEvent, handler)
world.publish(ActorImpulseEvent(...))
events = world.consume_published_events(ActorImpulseEvent)
world.unsubscribe(sub_id)
```

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
