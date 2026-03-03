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

## NPC agency flow

1. LLM returns actor registration/update payload.
2. Kernel maps that payload into `LLMActorRegistrationCommand`.
3. `LLMActorGatewaySystem` writes:
   - `LongTermGoals`
   - `FactionRelations`
   - `FactionTraits`
   - `InitiativeState` (turn cadence)
   - `CurrentAction` + `ActionHistory`
4. `ActorAgencySystem` selects eligible scene actors (2-3, respecting cooldown) and
   updates `ActorAgency`, `CurrentAction`, `ActionHistory`, and emits `ActorImpulseEvent`.

## Faction flow

1. LLM returns a faction payload mapped to `LLMFactionUpdateCommand`.
2. `LLMFactionGatewaySystem` writes:
   - `FactionHeat`
   - `GrandPlanClock` (progress + LLM-fillable `rate_per_turn`)
   - `FactionGoals` (`global_goals` + regional goals by region)
   - `FactionFlags` (gang-level flags/tags)
3. `FactionTickSystem` advances clocks each turn.
4. `LLMActorGatewaySystem` inherits `FactionFlags` into actor `FactionTraits` when
   the actor references a faction (`faction_entity_id`).

## Player agency (LLM integration)

1. LLM returns a player action payload mapped to `LLMPlayerAgencyCommand`.
2. `LLMPlayerAgencySystem` updates `CurrentAction` + `ActionHistory`.
3. It publishes `PlayerActionEvent` for kernel/external consumers.

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

## Grok REPL Troubleshooting

If Grok reports `ModuleNotFoundError: No module named 'ttrpg_engine'`:

```bash
PYTHONPATH=src python -c "from ecs import World; import ttrpg_engine; print('ok')"
```

If Grok session files were partially written/truncated, run:

```bash
python scripts/grok_repl_doctor.py
```

The doctor script validates that `src` is on `sys.path` and that core modules import
cleanly before you run turn logic.

To detect escaped/corrupted source blobs after a deploy/fetch step, run:

```bash
python scripts/check_source_integrity.py
```

This catches patterns like `text"""...`, `\__all__`, and single-line escaped source.

If those checks fail due to escaped package entrypoints, run:

```bash
python scripts/repair_escaped_init_files.py
python scripts/check_source_integrity.py
python scripts/grok_repl_doctor.py
```
