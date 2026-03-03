# Grok Living World Engine (Survival Roguelike Draft)

## Assumptions
- You want a **survival roguelike** where Grok is the fuzzy/creative layer and Python is the deterministic simulation layer.
- Runtime is a long-lived Python 3.12 REPL session (same instance survives multiple turns).
- Current repo is design-first; implementation files are not committed yet.

## Missing Critical Context (using safe defaults)
- Persistence backend preference (default recommendation: JSON snapshots first, optional SQLite later).
- Target scale (single-player default, no multi-user lock model yet).
- Replay strictness (default: deterministic RNG for all kernel decisions).

## Review of Your Updated Intention
Your provided kernel/plugin draft is directionally correct and already close to a buildable v0:
- The **Kernel/Plugin/LLM separation** is strong and should stay unchanged.
- The **`NeedsLLMFill` pull model** is the right way to keep LLM generation bounded and auditable.
- The **time chunk + volatility + interruption loop** is a good heartbeat for survival gameplay.
- `body_status` and lazy inventory generation fit roguelike emergent storytelling.

## Two Implementation Paths (pick one)

### Option A (Default): Deterministic-first
1. Implement kernel state machine + save/load + request idempotency.
2. Keep `Plugin5e` as a temporary stub.
3. Add Grok LLM fill points (`generate_location`, `batch_agendas`, `generate_interruption`, `generate_inventory`).

**Trade-off:** Slightly slower first demo, but stable saves and easier debugging.

### Option B: Content-first
1. Focus on location/NPC/inventory generation loops.
2. Keep mechanics shallow and improve later.

**Trade-off:** Faster wow-factor, but higher refactor risk when hardening saves/replay.

## Updated Architecture Contract (inferred from your code)

### 1) Hard boundary rules
- **LLM may suggest text/data only**; it never mutates world state directly.
- **Kernel is source of truth** for time, entity lifecycle, and persistence.
- **Plugin owns math** (`resolve_action`, `roll_dice`, volatility model, equipment validation).

### 2) Turn state machine (minimal)
Track a phase in world state:
- `IDLE`
- `WAITING_FOR_LLM`
- `RESOLVING`
- `COMMITTED`

This protects resume logic when a tool call is retried or duplicated.

### 3) LLM request envelope (recommended)
Use one envelope shape for all fills:
```json
{
  "needs_llm": true,
  "request_id": "uuid",
  "turn_id": 12,
  "request_type": "generate_location",
  "context": {},
  "schema": {},
  "schema_version": "1.0"
}
```

Resume rules:
- reject unknown `request_id`
- reject already-applied `request_id`
- validate payload keys/types before apply

### 4) Survival roguelike-specific data extensions
Your current models are good; add these small fields when implementing:
- `Actor`: `hunger`, `thirst`, `fatigue`, `temperature`, `infection_risk`
- `Location`: `hazards`, `resource_nodes`, `weather_profile`
- `Fact`: `confidence`, `created_minute`, `status` (`active|retracted|superseded`)

Keep them plugin-agnostic by storing as tags/stats dictionaries where possible.

### 5) Interrupt loop hardening
Keep your existing flow and add:
- kernel-seeded RNG for deterministic interruption selection
- interruption cooldown floor to prevent spam chains
- log tuple: `(turn_id, danger, candidates, selected)` for replay diagnosis

### 6) Save/Load contract (new)
Add `serialize_world()` and `deserialize_world()` with versioning.

#### JSON snapshot (recommended first)
```json
{
  "save_version": 1,
  "world": {
    "time_minutes": 180,
    "current_location": "The Salty Wench",
    "last_interrupt_time": 120,
    "tension_cooldown": 30,
    "phase": "COMMITTED",
    "turn_id": 44,
    "rng_seed": 1337,
    "rng_draws": 92
  },
  "actors": [],
  "locations": [],
  "facts": [],
  "next_uid": 1032,
  "pending_llm": {}
}
```

#### Deserialize requirements
- fail loudly on missing required keys (`save_version`, `world`, `actors`, `locations`)
- migrate older `save_version` before object construction
- verify plugin compatibility (`api_version` / capability set)

### 7) YAML support
Support YAML only as an optional export/import format.
Default runtime save format should remain JSON for deterministic and dependency-light behavior.

## Minimal Build Plan (survival-focused)
1. **M1:** Kernel models + deterministic RNG + `serialize_world`/`deserialize_world`.
2. **M2:** `NeedsLLMFill` request registry (`request_id`, idempotent apply).
3. **M3:** survival tick effects (hunger/thirst/fatigue) in plugin-neutral loop.
4. **M4:** Grok-driven generation for location/NPC/inventory.
5. **M5:** real rules plugin and combat injury consequences.

## Backward Compatibility Note
No runtime API exists in-repo yet, so this document is non-breaking.
When code lands, freeze interfaces as `v0.1` and only add backward-compatible fields to save files; migrate everything else.

## Security and Validation
- Treat every LLM response as untrusted input.
- Validate against explicit schema before apply.
- Never log secrets/user identifiers in world snapshots.

## Rollback
- Revert to previous commit if architecture direction changes.
- Keep save migrations append-only so old saves remain recoverable.
