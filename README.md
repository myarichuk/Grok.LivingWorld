# Grok LivingWorld ECS

Lightweight ECS primitives with modular systems that each return an LLM-forwardable object.

## Structure

- `src/livingworld_ecs/core.py` – ECS world, system protocol, and global aggregator.
- `src/livingworld_ecs/components.py` – sample component dataclasses.
- `src/livingworld_ecs/systems.py` – sample systems returning structured payloads.
- `tests/` – unit tests covering world operations, per-system outputs, and aggregation.
- `scripts/setup.sh` and `scripts/setup.ps1` – Unix/PowerShell virtual environment bootstrap.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

```python
from livingworld_ecs import (
    GlobalSystem,
    Health,
    HealthSummarySystem,
    Position,
    SpatialSummarySystem,
    World,
)

world = World()
entity = world.create_entity()
world.add_component(entity, Health(current=8, maximum=10))
world.add_component(entity, Position(x=1.0, y=3.0))

global_system = GlobalSystem([HealthSummarySystem(), SpatialSummarySystem()])
results = global_system.run(world)

for result in results:
    print(result.to_dict())
```

## Development checks

```bash
ruff check .
pytest
```
