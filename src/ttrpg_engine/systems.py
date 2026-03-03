"""Systems implementing the turn state machine and LLM-fill flow."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ecs.core import EntityId, SystemResult, World
from ttrpg_engine.components import (
    EndTurnCommand,
    KernelState,
    LLMResponse,
    NeedsLLMFill,
    RequestRegistry,
    ResolvedLLMResult,
    StartTurnCommand,
    TurnPhase,
)


@dataclass
class StartTurnSystem:
    name: str = "start_turn"
    required_components: tuple[type[object], ...] = (
        KernelState,
        RequestRegistry,
        StartTurnCommand,
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
    required_components: tuple[type[object], ...] = (
        KernelState,
        RequestRegistry,
        LLMResponse,
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
    required_components: tuple[type[object], ...] = (KernelState, RequestRegistry)

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
    required_components: tuple[type[object], ...] = (KernelState, EndTurnCommand)

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
