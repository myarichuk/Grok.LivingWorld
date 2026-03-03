"""Systems implementing the turn state machine and LLM-fill flow."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ecs.core import EntityId, EntityQuery, SystemResult, World
from ttrpg_engine.components import (
    ActorAgency,
    ActorComponent,
    ActorImpulse,
    EndTurnCommand,
    FactionRelations,
    KernelState,
    LLMActorRegistrationCommand,
    LLMResponse,
    LongTermGoals,
    NarrativeActor,
    NeedsLLMFill,
    RequestRegistry,
    ResolvedLLMResult,
    ScenePresence,
    StartTurnCommand,
    TurnPhase,
)
from ttrpg_engine.events import ActorImpulseEvent, ActorRegisteredEvent


@dataclass
class StartTurnSystem:
    name: str = "start_turn"
    query: EntityQuery = EntityQuery(
        all_of=(
            KernelState,
            RequestRegistry,
            StartTurnCommand,
        )
    )

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        started: list[dict[str, object]] = []
        rejected: list[dict[str, object]] = []

        for command_entity in entities:
            state = world.get_component(command_entity, KernelState)
            registry = world.get_component(command_entity, RequestRegistry)
            command = world.get_component(command_entity, StartTurnCommand)

            if state.phase != TurnPhase.IDLE:
                rejected.append(
                    {
                        "kernel_entity": command_entity,
                        "reason": f"phase must be IDLE, got {state.phase.value}",
                    }
                )
                world.remove_component(command_entity, StartTurnCommand)
                continue

            next_turn_id = state.turn_id + 1
            request_id = _next_request_id(
                turn_id=next_turn_id,
                request_type=command.request_type,
                existing_ids=set(registry.pending_request_ids)
                | set(registry.applied_request_ids),
            )

            request_entity = world.create_entity()
            world.add_component(
                request_entity,
                NeedsLLMFill(
                    request_id=request_id,
                    turn_id=next_turn_id,
                    request_type=command.request_type,
                    context=command.context,
                    schema=command.schema,
                    schema_version=command.schema_version,
                ),
            )

            world.add_component(
                command_entity,
                replace(
                    state,
                    phase=TurnPhase.WAITING_FOR_LLM,
                    turn_id=next_turn_id,
                    pending_time_advance_minutes=state.pending_time_advance_minutes
                    + max(command.advance_minutes, 0),
                ),
            )
            world.add_component(
                command_entity,
                replace(
                    registry,
                    pending_request_ids=registry.pending_request_ids + (request_id,),
                ),
            )
            world.remove_component(command_entity, StartTurnCommand)

            started.append(
                {
                    "kernel_entity": command_entity,
                    "request_entity": request_entity,
                    "request_id": request_id,
                    "turn_id": next_turn_id,
                }
            )

        return SystemResult(
            self.name,
            len(entities),
            {
                "started": started,
                "rejected": rejected,
            },
        )


@dataclass
class ApplyLLMResponseSystem:
    name: str = "apply_llm_response"
    query: EntityQuery = EntityQuery(
        all_of=(
            KernelState,
            RequestRegistry,
            LLMResponse,
        )
    )

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        requests_by_id = {
            world.get_component(entity, NeedsLLMFill).request_id: (
                entity,
                world.get_component(entity, NeedsLLMFill),
            )
            for entity in world.query_entities((NeedsLLMFill,))
        }

        applied: list[dict[str, object]] = []
        rejected: list[dict[str, object]] = []

        for response_entity in entities:
            state = world.get_component(response_entity, KernelState)
            registry = world.get_component(response_entity, RequestRegistry)
            response = world.get_component(response_entity, LLMResponse)
            request_ref = requests_by_id.get(response.request_id)

            if response.request_id in registry.applied_request_ids:
                rejected.append(
                    {
                        "kernel_entity": response_entity,
                        "request_id": response.request_id,
                        "reason": "request already applied",
                    }
                )
                world.remove_component(response_entity, LLMResponse)
                continue

            if request_ref is None:
                rejected.append(
                    {
                        "kernel_entity": response_entity,
                        "request_id": response.request_id,
                        "reason": "unknown request_id",
                    }
                )
                world.remove_component(response_entity, LLMResponse)
                continue

            request_entity, request = request_ref
            missing_keys = _missing_required_keys(
                payload=response.payload,
                schema=request.schema,
            )
            if missing_keys:
                rejected.append(
                    {
                        "kernel_entity": response_entity,
                        "request_id": response.request_id,
                        "reason": f"payload missing required keys: {missing_keys}",
                    }
                )
                world.remove_component(response_entity, LLMResponse)
                continue

            result_entity = world.create_entity()
            world.add_component(
                result_entity,
                ResolvedLLMResult(
                    request_id=request.request_id,
                    request_type=request.request_type,
                    turn_id=request.turn_id,
                    payload=response.payload,
                ),
            )

            next_pending = tuple(
                request_id
                for request_id in registry.pending_request_ids
                if request_id != request.request_id
            )
            next_applied = registry.applied_request_ids + (request.request_id,)
            next_phase = (
                TurnPhase.RESOLVING if not next_pending else TurnPhase.WAITING_FOR_LLM
            )

            world.add_component(
                response_entity,
                replace(state, phase=next_phase),
            )
            world.add_component(
                response_entity,
                replace(
                    registry,
                    pending_request_ids=next_pending,
                    applied_request_ids=next_applied,
                ),
            )

            world.destroy_entity(request_entity)
            world.remove_component(response_entity, LLMResponse)

            applied.append(
                {
                    "kernel_entity": response_entity,
                    "result_entity": result_entity,
                    "request_id": request.request_id,
                }
            )

        return SystemResult(
            self.name,
            len(entities),
            {
                "applied": applied,
                "rejected": rejected,
            },
        )


@dataclass
class CommitTurnSystem:
    name: str = "commit_turn"
    query: EntityQuery = EntityQuery(all_of=(KernelState, RequestRegistry))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        committed: list[int] = []

        for entity in entities:
            state = world.get_component(entity, KernelState)
            registry = world.get_component(entity, RequestRegistry)
            if state.phase != TurnPhase.RESOLVING:
                continue
            if registry.pending_request_ids:
                continue

            world.add_component(
                entity,
                replace(
                    state,
                    phase=TurnPhase.COMMITTED,
                    time_minutes=(
                        state.time_minutes + state.pending_time_advance_minutes
                    ),
                    pending_time_advance_minutes=0,
                ),
            )
            committed.append(entity)

        return SystemResult(
            self.name,
            len(entities),
            {
                "committed_entities": committed,
            },
        )


@dataclass
class EndTurnSystem:
    name: str = "end_turn"
    query: EntityQuery = EntityQuery(all_of=(KernelState, EndTurnCommand))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        ended: list[int] = []
        rejected: list[dict[str, object]] = []

        for entity in entities:
            state = world.get_component(entity, KernelState)
            if state.phase != TurnPhase.COMMITTED:
                rejected.append(
                    {
                        "kernel_entity": entity,
                        "reason": f"phase must be COMMITTED, got {state.phase.value}",
                    }
                )
                world.remove_component(entity, EndTurnCommand)
                continue

            world.add_component(entity, replace(state, phase=TurnPhase.IDLE))
            world.remove_component(entity, EndTurnCommand)
            ended.append(entity)

        return SystemResult(
            self.name,
            len(entities),
            {
                "ended": ended,
                "rejected": rejected,
            },
        )


@dataclass
class ActorAgencySystem:
    """Select 2-3 actors in the current scene and execute impulse actions."""

    name: str = "actor_agency"
    query: EntityQuery = EntityQuery(all_of=(KernelState,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        processed: list[dict[str, object]] = []

        for kernel_entity in entities:
            state = world.get_component(kernel_entity, KernelState)
            actor_entities = world.query(
                EntityQuery(all_of=(ActorComponent, ActorAgency, ScenePresence))
            )
            candidates = [
                actor_entity
                for actor_entity in actor_entities
                if world.get_component(actor_entity, ScenePresence).scene_id
                == state.current_location
            ]

            if not candidates:
                processed.append(
                    {
                        "kernel_entity": kernel_entity,
                        "selected_actor_ids": [],
                        "impulse_entity_ids": [],
                    }
                )
                continue

            selection_count = min(
                len(candidates),
                2 + ((state.turn_id + state.rng_draws) % 2),
            )
            if len(candidates) == 1:
                selection_count = 1

            rng = random.Random(state.rng_seed + state.turn_id + state.rng_draws)
            selected = sorted(rng.sample(candidates, selection_count))

            impulse_entity_ids: list[int] = []
            for actor_entity in selected:
                agency = world.get_component(actor_entity, ActorAgency)
                goal = _select_goal(agency, state.turn_id, actor_entity)
                impulse = _build_impulse(goal)

                world.add_component(
                    actor_entity,
                    replace(
                        agency,
                        short_term_goal=goal,
                        impulse=impulse,
                        last_impulse_turn=state.turn_id,
                    ),
                )

                impulse_entity = world.create_entity()
                world.add_component(
                    impulse_entity,
                    ActorImpulse(
                        actor_entity_id=actor_entity,
                        turn_id=state.turn_id,
                        scene_id=state.current_location,
                        goal=goal,
                        impulse=impulse,
                    ),
                )
                world.publish(
                    ActorImpulseEvent(
                        actor_entity_id=actor_entity,
                        target_entity_id=None,
                        scene_id=state.current_location,
                        turn_id=state.turn_id,
                        impulse=impulse,
                        source=self.name,
                    )
                )
                impulse_entity_ids.append(impulse_entity)

            world.add_component(
                kernel_entity,
                replace(state, rng_draws=state.rng_draws + len(selected)),
            )
            processed.append(
                {
                    "kernel_entity": kernel_entity,
                    "selected_actor_ids": selected,
                    "impulse_entity_ids": impulse_entity_ids,
                }
            )

        return SystemResult(
            self.name,
            len(entities),
            {"processed": processed},
        )


@dataclass
class LLMActorGatewaySystem:
    """Register/update actors from LLM data and derive next impulse."""

    name: str = "llm_actor_gateway"
    query: EntityQuery = EntityQuery(all_of=(LLMActorRegistrationCommand,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        kernels = world.query(EntityQuery(all_of=(KernelState,)))
        current_turn = (
            world.get_component(kernels[0], KernelState).turn_id if kernels else -1
        )

        registered: list[dict[str, object]] = []
        for command_entity in entities:
            command = world.get_component(command_entity, LLMActorRegistrationCommand)

            actor_entity = command.actor_entity_id
            if actor_entity is None:
                actor_entity = world.create_entity()
                world.add_component(
                    actor_entity,
                    NarrativeActor(name=command.actor_name, kind=command.actor_kind),
                )

            sanitized_relations = _sanitize_faction_relations(command.faction_relations)
            world.add_component(actor_entity, ScenePresence(scene_id=command.scene_id))
            world.add_component(
                actor_entity,
                LongTermGoals(goals=command.long_term_goals),
            )
            world.add_component(
                actor_entity,
                FactionRelations(standings=sanitized_relations),
            )

            short_term_goal = _derive_short_term_goal(
                command.long_term_goals, command.possible_goals
            )
            impulse = (
                command.suggested_impulse
                or _derive_impulse_from_context(
                    goal=short_term_goal,
                    faction_relations=sanitized_relations,
                )
            )
            agency_goals = command.possible_goals or command.long_term_goals
            world.add_component(
                actor_entity,
                ActorAgency(
                    possible_goals=agency_goals,
                    short_term_goal=short_term_goal,
                    impulse=impulse,
                    last_impulse_turn=current_turn,
                ),
            )

            world.publish(
                ActorRegisteredEvent(
                    actor_entity_id=actor_entity,
                    actor_name=command.actor_name,
                    scene_id=command.scene_id,
                    long_term_goals=command.long_term_goals,
                    faction_relations=sanitized_relations,
                )
            )
            world.publish(
                ActorImpulseEvent(
                    actor_entity_id=actor_entity,
                    target_entity_id=None,
                    scene_id=command.scene_id,
                    turn_id=current_turn,
                    impulse=impulse,
                    source=self.name,
                )
            )
            world.remove_component(command_entity, LLMActorRegistrationCommand)

            registered.append(
                {
                    "command_entity": command_entity,
                    "actor_entity": actor_entity,
                    "short_term_goal": short_term_goal,
                    "impulse": impulse,
                }
            )

        return SystemResult(
            self.name,
            len(entities),
            {"registered": registered},
        )


def _next_request_id(turn_id: int, request_type: str, existing_ids: set[str]) -> str:
    base = f"turn-{turn_id}-{request_type}"
    if base not in existing_ids:
        return base

    index = 1
    while True:
        candidate = f"{base}-{index}"
        if candidate not in existing_ids:
            return candidate
        index += 1


def _missing_required_keys(
    payload: dict[str, object], schema: dict[str, object]
) -> list[str]:
    required = schema.get("required", [])
    if not isinstance(required, list):
        return []

    missing: list[str] = []
    for key in required:
        if isinstance(key, str) and key not in payload:
            missing.append(key)
    return missing


def _select_goal(agency: ActorAgency, turn_id: int, actor_entity: int) -> str:
    if agency.short_term_goal:
        return agency.short_term_goal
    if agency.possible_goals:
        index = (turn_id + actor_entity) % len(agency.possible_goals)
        return agency.possible_goals[index]
    return "assess nearby threats"


def _build_impulse(goal: str) -> str:
    normalized = goal.lower()
    if "protect" in normalized or "guard" in normalized:
        return "moves to cover and guards allies"
    if "find" in normalized or "search" in normalized:
        return "scans the scene and searches likely spots"
    if "escape" in normalized or "flee" in normalized:
        return "pulls back toward safer ground"
    return f"acts toward goal: {goal}"


def _derive_short_term_goal(
    long_term_goals: tuple[str, ...], possible_goals: tuple[str, ...]
) -> str:
    if possible_goals:
        return possible_goals[0]
    if long_term_goals:
        return long_term_goals[0]
    return "maintain position"


def _sanitize_faction_relations(relations: dict[str, int]) -> dict[str, int]:
    return {
        faction: max(-100, min(100, int(score)))
        for faction, score in relations.items()
    }


def _derive_impulse_from_context(goal: str, faction_relations: dict[str, int]) -> str:
    hostile_factions = [
        faction for faction, score in faction_relations.items() if score < 0
    ]
    allied_factions = [
        faction for faction, score in faction_relations.items() if score > 0
    ]
    if hostile_factions:
        return (
            f"pursues '{goal}' while watching {hostile_factions[0]} for retaliation"
        )
    if allied_factions:
        return f"pursues '{goal}' and coordinates with {allied_factions[0]}"
    return f"pursues '{goal}' cautiously"
