# Grok Living World Engine Design (Current + Next)

## Current Runtime Reality
- The codebase is implementation-first now (`src/ecs`, `src/ttrpg_engine`, `src/ttrpg_5e`, tests).
- ECS world state is persisted via `WorldDB` append-only storage and rehydrated on startup.
- Unified runtime flow exists (`scripts/grok_prepare_unified_runtime.py` -> `scripts/grok_unified_engine.py`).
- Kernel turn phases are implemented (`IDLE`, `WAITING_FOR_LLM`, `RESOLVING`, `COMMITTED`).
- LLM writes through command components and systems, never direct world mutation.

## Existing Contracts to Preserve
- Deterministic kernel owns time, turn progression, and authoritative state.
- LLM is an untrusted suggestion layer; payloads are schema-validated before apply.
- Requests are idempotent via `request_id` tracking in `RequestRegistry`.
- ECS + WorldDB remain the persistence and query backbone.

## NPC Lifecycle Model (New)

### NPC Residency Types
- `transient` (travelers/commoners): short-lived scene occupants intended to churn.
- `persistent` (named world actors): long-lived actors kept across scene/time transitions.

### Required NPC Metadata
- `residency_type`: `transient|persistent`
- `spawn_turn_id`
- `last_seen_turn_id`
- `transient_timeout_turns` (only for transient)
- `known_to_pc` (bool): whether the PC has meaningfully interacted and may see stable identity in narrative
- `display_name`: optional when unknown; if `known_to_pc=false`, narrative can show role/description instead of true name

### Cleanup Rules
- At each turn commit, evaluate all transient NPCs in active and cached scenes.
- Remove transient NPC from `LocationOccupancy` when:
  - `current_turn - last_seen_turn_id >= transient_timeout_turns`, or
  - scene capacity pressure requires eviction of lowest-priority transients.
- Cleanup is soft-delete at gameplay level (out of scene), not hard delete from history.

### Promotion Flow (Transient -> Persistent)
- If PC interacts with a transient NPC, the engine must emit a structured interaction record.
- LLM can decide to promote the NPC to persistent.
- Promotion keeps same `actor_entity_id` and converts lifecycle metadata:
  - `residency_type=persistent`
  - `transient_timeout_turns=null`
  - optional explicit `NarrativeActor.name` update
  - optional faction/goal/relationship enrichment

## LLM Query and Registration Surface (New)

### Query Intents for LLM
- `query_scene_actors`
  - filters: `scene_id`, `residency_type`, `known_to_pc`, tags, distance bucket
  - returns compact roster with stable ids and minimal relationship summary
- `query_transient_interactions`
  - filters: `turn_range`, `scene_id`, `pc_entity_id`
  - returns transient NPCs recently interacted with and promotion candidates
- `query_relationship_graph`
  - filters: `actor_entity_id`, `bucket`, `depth`, relationship tags
  - returns neighbor list/edges, optionally aggregated counts by bucket

### Registration/Mutation Intents for LLM
- `register_npc`
  - create actor + occupancy + lifecycle metadata in one command payload
- `update_npc_lifecycle`
  - update timeout, last_seen_turn_id, known_to_pc, tags
- `promote_npc_to_persistent`
  - allowed only for existing transient actor ids
- `upsert_relationship_edge`
  - create or update relationship edge (source, target, bucket, tags, score, rationale)

## Relationship Model (New)

### Relationship Buckets
- `hater`
- `enemy`
- `rival`
- `acquaintance`
- `friend`
- `ally`
- `trusted`

### Edge Schema
- `source_actor_entity_id`
- `target_actor_entity_id`
- `bucket` (enum above)
- `score` (optional numeric refinement, e.g. -100..100)
- `tags` (lightweight query handles, e.g. `debt`, `family`, `betrayal`, `mentor`, `romance`)
- `last_updated_turn_id`
- `visibility`: `private|rumor|public`
- `known_to_pc` (whether PC should receive explicit narrative disclosure)

### Graph Storage + Persistence
- Store relationship edges as ECS components/events and persist through `WorldDB` journal.
- Keep denormalized query tags on edge payload to avoid expensive full scans.
- Maintain both directional edges when needed (`A->B` and `B->A`) rather than inferring symmetry.

## Efficient LLM Query Strategy
- Index relationship terms/tags and scene ids in WorldDB documents.
- Standardize tag prefixes for fast filtering:
  - `rel_bucket:<bucket>`
  - `rel_tag:<tag>`
  - `actor:<id>`
  - `scene:<scene_id>`
  - `npc_type:transient|persistent`
  - `known_to_pc:true|false`
- Favor compact query responses (ids + buckets + key tags) and let LLM request expansion on demand.

## Narrative Rules Tied to `known_to_pc`
- If `known_to_pc=false`, narrative should default to role descriptors.
- After interaction crossing a threshold, set `known_to_pc=true` and allow stable naming.
- Promotion to persistent can happen before or after known status flips; they are related but not identical.

## Required Eventing
- Emit events for:
  - transient timeout cleanup/removal
  - transient interaction with PC (promotion candidate signal)
  - promotion to persistent
  - relationship edge upsert/bucket change
- Persist these events via the existing ECS event journal path.

## Incremental Implementation Plan
1. Add lifecycle components and timeout cleanup system.
2. Add transient interaction event + promotion command/system.
3. Add relationship edge component(s) + graph query system.
4. Add LLM query/register request types and schema validation.
5. Add persistence and rehydration tests for lifecycle and relationships.
