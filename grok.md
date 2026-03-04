# Grok Bootstrap Guide

Primary REPL path: use one unified runtime script (`scripts/grok_unified_engine.py`) that embeds all project modules in one file and serves them via in-memory imports (no filesystem writes).

Filesystem path: `scripts/grok_src_dropper.py` writes all `src/*.py` files in one run.

Hardened filesystem path: `scripts/grok_repl_bundle.py` adds extra hash/doctor checks.

Fallback path: raw `src/*.py` download list is kept below.

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
- `src/ttrpg_engine/components/player.py`
- `src/ttrpg_engine/events.py`
- `src/ttrpg_engine/systems.py`

## Raw Link List (GitHub)

Use one raw URL per path. Replace `<REF>` with a pinned commit SHA (if specified by user) or `main`.

- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ecs/__init__.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ecs/core.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_5e/__init__.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_5e/components.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_5e/factory.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/__init__.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/components/__init__.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/components/actor.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/components/faction.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/components/kernel.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/components/llm.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/components/player.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/events.py`
- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/src/ttrpg_engine/systems.py`

## Preferred Bootstrap (Unified Runtime, No File Writes)

1. Generate unified runtime in repo root:

```bash
python scripts/grok_prepare_unified_runtime.py
```

2. Download generated file in Grok target:

- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/scripts/grok_unified_engine.py`

3. Run importer smoke check:

```bash
python grok_unified_engine.py --check
```

Expected output:

- `importer=installed`
- `check=ok`

4. Use inside Python session:

```python
import grok_unified_engine as engine
engine.install_importer()

from ecs import World
from ttrpg_engine import KernelState, TurnPhase
from ttrpg_5e import Actor5eFactory
```

## Filesystem Bootstrap (Plain Single File)

1. Generate the dropper in repo root:

```bash
python scripts/grok_prepare_single_file.py
```

2. Download generated file in Grok target:

- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/scripts/grok_src_dropper.py`

3. Run dropper:

```bash
python grok_src_dropper.py --root .
```

Expected output:

- `install=ok`
- `verify=ok`

## Hardened Bootstrap (Single File + Hash/Doctor)

1. Download bundle script:

- `https://raw.githubusercontent.com/myarichuk/Grok.LivingWorld/<REF>/scripts/grok_repl_bundle.py`

2. Run bundle in target root:

```bash
python grok_repl_bundle.py --root .
```

Expected output:

- `install=ok`
- `verify=ok`
- `doctor=ok`

3. Optional checks from repo (if scripts are present):

```bash
python scripts/check_source_integrity.py
python scripts/grok_repl_doctor.py
pytest
```

## Fallback Bootstrap (Raw Files)

1. Create project root and directories:

```bash
mkdir -p src/ecs src/ttrpg_5e src/ttrpg_engine/components scripts tests
```

2. For each URL in the raw link list:
- Convert URL path after `/<REF>/` into local path.
- Create parent directory (`mkdir -p "$(dirname "$path")"`).
- Download bytes exactly to file (no escaping, no JSON/string wrapping).

3. Verify file integrity:

```bash
python scripts/check_source_integrity.py
```

4. If integrity fails due escaped blobs, repair package entrypoints and recheck:

```bash
python scripts/repair_escaped_init_files.py
python scripts/check_source_integrity.py
```

5. Bootstrap imports for REPL:

```bash
python scripts/grok_repl_doctor.py
```

6. Run tests when available:

```bash
pytest
```

## Important Rules for Grok

- Do not serialize file bodies as escaped strings.
- Write raw text with real newlines.
- Do not prepend helper text like `text` before Python module docstrings.
- Preserve ASCII exactly as in source.
- Prefer pinned commit SHA in `<REF>` for reproducible deployments.
- Prefer single-file install (`scripts/grok_unified_engine.py`, `scripts/grok_src_dropper.py`, or `scripts/grok_repl_bundle.py`) over per-file raw fetch.
