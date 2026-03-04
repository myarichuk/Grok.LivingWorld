# Grok Bootstrap Guide

Use only one file in Grok REPL deployments:

- `scripts/grok_unified_engine.py`

Do not use `grok_src_dropper.py`, `grok_repl_bundle.py`, or per-file raw `src/` downloads for Grok.

## Maintain This List

- If any new Python file is added under `src/`, update this file in the same commit.
- If any file is removed/renamed, update this file immediately.
- Keep paths sorted lexicographically.
- Regenerate with:

```bash
find src -type f -name '*.py' | sort
```

## Source File Paths (`src/*.py`)

- `src/ecs/__init__.py`
- `src/ecs/core.py`
- `src/ttrpg_5e/__init__.py`
- `src/ttrpg_5e/components.py`
- `src/ttrpg_5e/factory.py`
- `src/ttrpg_engine/__init__.py`
- `src/ttrpg_engine/components/__init__.py`
- `src/ttrpg_engine/components/actor.py`
- `src/ttrpg_engine/components/faction.py`
- `src/ttrpg_engine/components/kernel.py`
- `src/ttrpg_engine/components/llm.py`
- `src/ttrpg_engine/components/location.py`
- `src/ttrpg_engine/components/player.py`
- `src/ttrpg_engine/events.py`
- `src/ttrpg_engine/systems.py`
- `src/ttrpg_engine/world_db.py`

## Unified Runtime Only

1. Generate unified runtime in repo root:

```bash
python scripts/grok_prepare_unified_runtime.py
```

2. Download generated file in Grok target:

- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/scripts/grok_unified_engine.py`

3. Run importer smoke checks:

```bash
python grok_unified_engine.py --check --check-all
```

Expected output:

- `importer=installed`
- `check=ok`
- `check_all=ok`

4. Use inside Python session:

```python
import grok_unified_engine as engine
engine.install_importer()

from ecs import World
from ttrpg_engine import KernelState, TurnPhase
from ttrpg_5e import Actor5eFactory
```

## Important Rules for Grok

- Use only `scripts/grok_unified_engine.py`.
- Do not serialize module bodies as escaped strings.
- Preserve source text with real newlines.
- Prefer pinned commit SHA in `<REF>` for reproducible deployments.
