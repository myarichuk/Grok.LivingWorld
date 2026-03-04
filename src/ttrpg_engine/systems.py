"""Systems implementing the turn state machine and LLM-fill flow."""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ecs.core import EntityId, EntityQuery, SystemResult, World
from ttrpg_engine.components import (
    ActionHistory,
    ActionRecord,
    ActorAgency,
    ActorComponent,
    ActorImpulse,
    CurrentAction,
    DistanceBucket,
    EndTurnCommand,
    Faction,
    FactionFlags,
    FactionGoals,
    FactionHeat,
    FactionMembership,
    FactionRelations,
    FactionTraits,
    GrandPlanClock,
    InitiativeState,
    KernelState,
    LLMActorRegistrationCommand,
    LLMFactionUpdateCommand,
    LLMPlayerAgencyCommand,
    LLMResponse,
    Location,
    LocationOccupancy,
    LongTermGoals,
    MoveActorLocationCommand,
    NarrativeActor,
    NeedsLLMFill,
    PlayerActor,
    RegisterActorLocationCommand,
    RequestRegistry,
    ResolvedLLMResult,
    ScenePosition,
    ScenePresence,
    StartTurnCommand,
    TurnPhase,
)
from ttrpg_engine.events import (
    ActorImpulseEvent,
    ActorLocationChangedEvent,
    ActorRegisteredEvent,
    FactionUpdatedEvent,
    PlayerActionEvent,
)

_DISTANCE_PRIORITY: dict[DistanceBucket, int] = {
    DistanceBucket.ENGAGED: 0,
    DistanceBucket.CLOSE: 1,
    DistanceBucket.NEAR: 2,
    DistanceBucket.FAR: 3,
    DistanceBucket.DISTANT: 4,
}


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
        """Transition kernels from IDLE into WAITING_FOR_LLM with request envelope."""
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
        """Apply validated LLM responses and advance kernel request state."""
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
        """Commit a resolving turn once all pending LLM requests are applied."""
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
        """Move committed kernels back to IDLE once end-turn command is present."""
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
class LocationRegistrationSystem:
    """Register actors into location occupancy and scene position state."""

    name: str = "location_registration"
    query: EntityQuery = EntityQuery(all_of=(RegisterActorLocationCommand,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Register actor presence in a scene and keep occupancy lists in sync."""
        registered: list[dict[str, object]] = []
        rejected: list[dict[str, object]] = []

        for command_entity in entities:
            command = world.get_component(command_entity, RegisterActorLocationCommand)
            actor_entity = command.actor_entity_id

            if not world.has_component(actor_entity, ActorComponent):
                rejected.append(
                    {
                        "command_entity": command_entity,
                        "actor_entity": actor_entity,
                        "reason": "actor is missing ActorComponent",
                    }
                )
                world.remove_component(command_entity, RegisterActorLocationCommand)
                continue

            from_scene = _get_actor_scene_id(world, actor_entity)
            to_scene = command.scene_id
            zone = command.zone.strip() or "default"
            bucket = _parse_distance_bucket(command.distance_bucket)

            _assign_actor_location(
                world=world,
                actor_entity=actor_entity,
                to_scene_id=to_scene,
                zone=zone,
                distance_bucket=bucket,
            )
            world.remove_component(command_entity, RegisterActorLocationCommand)

            if from_scene and from_scene != to_scene:
                world.publish(
                    ActorLocationChangedEvent(
                        actor_entity_id=actor_entity,
                        from_scene_id=from_scene,
                        to_scene_id=to_scene,
                        to_zone=zone,
                        to_distance_bucket=bucket.value,
                        source=self.name,
                    )
                )

            registered.append(
                {
                    "command_entity": command_entity,
                    "actor_entity": actor_entity,
                    "scene_id": to_scene,
                    "zone": zone,
                    "distance_bucket": bucket.value,
                    "from_scene_id": from_scene,
                }
            )

        return SystemResult(
            self.name,
            len(entities),
            {"registered": registered, "rejected": rejected},
        )


@dataclass
class ActorLocationChangeSystem:
    """Move actors between scene locations and update occupancy."""

    name: str = "actor_location_change"
    query: EntityQuery = EntityQuery(all_of=(MoveActorLocationCommand,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Apply move commands and publish location-change events."""
        moved: list[dict[str, object]] = []
        rejected: list[dict[str, object]] = []

        for command_entity in entities:
            command = world.get_component(command_entity, MoveActorLocationCommand)
            actor_entity = command.actor_entity_id
            if not world.has_component(actor_entity, ActorComponent):
                rejected.append(
                    {
                        "command_entity": command_entity,
                        "actor_entity": actor_entity,
                        "reason": "actor is missing ActorComponent",
                    }
                )
                world.remove_component(command_entity, MoveActorLocationCommand)
                continue

            from_scene = _get_actor_scene_id(world, actor_entity)
            to_scene = command.to_scene_id
            zone = command.to_zone.strip() or "default"
            bucket = _parse_distance_bucket(command.to_distance_bucket)

            _assign_actor_location(
                world=world,
                actor_entity=actor_entity,
                to_scene_id=to_scene,
                zone=zone,
                distance_bucket=bucket,
            )
            _sync_kernel_location_for_player(world, actor_entity, to_scene)
            world.remove_component(command_entity, MoveActorLocationCommand)

            world.publish(
                ActorLocationChangedEvent(
                    actor_entity_id=actor_entity,
                    from_scene_id=from_scene,
                    to_scene_id=to_scene,
                    to_zone=zone,
                    to_distance_bucket=bucket.value,
                    source=self.name,
                )
            )

            moved.append(
                {
                    "command_entity": command_entity,
                    "actor_entity": actor_entity,
                    "from_scene_id": from_scene,
                    "to_scene_id": to_scene,
                    "zone": zone,
                    "distance_bucket": bucket.value,
                }
            )

        return SystemResult(
            self.name,
            len(entities),
            {"moved": moved, "rejected": rejected},
        )


@dataclass
class ActorAgencySystem:
    """Select 2-3 actors in the current scene and execute impulse actions."""

    name: str = "actor_agency"
    query: EntityQuery = EntityQuery(all_of=(KernelState,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Select 2-3 eligible actors and record their next impulse/action."""
        processed: list[dict[str, object]] = []

        for kernel_entity in entities:
            state = world.get_component(kernel_entity, KernelState)
            actor_entities = world.query(
                EntityQuery(all_of=(ActorComponent, ActorAgency, ScenePresence))
            )
            candidates: list[tuple[int, int]] = []
            for actor_entity in actor_entities:
                scene_position = _get_or_create_scene_position(world, actor_entity)
                if scene_position.scene_id != state.current_location:
                    continue

                initiative = _get_or_create_initiative_state(world, actor_entity)
                turns_since = _compute_turns_since_last_impulse(
                    turn_id=state.turn_id,
                    initiative=initiative,
                )
                world.add_component(
                    actor_entity,
                    replace(initiative, turns_since_last_impulse=turns_since),
                )
                if turns_since >= initiative.min_turns_between_impulses:
                    priority = _DISTANCE_PRIORITY[scene_position.distance_bucket]
                    candidates.append((priority, actor_entity))

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
            rng.shuffle(candidates)
            ranked = sorted(candidates, key=lambda item: item[0])
            selected = sorted(
                actor_entity
                for _, actor_entity in ranked[:selection_count]
            )

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
                world.add_component(
                    actor_entity,
                    CurrentAction(
                        description=impulse,
                        source=self.name,
                        turn_id=state.turn_id,
                    ),
                )
                _append_action_history(
                    world=world,
                    actor_entity=actor_entity,
                    record=ActionRecord(
                        turn_id=state.turn_id,
                        action=impulse,
                        source=self.name,
                        note=f"goal={goal}",
                    ),
                )
                world.add_component(
                    actor_entity,
                    replace(
                        world.get_component(actor_entity, InitiativeState),
                        last_impulse_turn=state.turn_id,
                        turns_since_last_impulse=0,
                    ),
                )

                impulse_entity = world.create_entity()
                position = world.get_component(actor_entity, ScenePosition)
                world.add_component(
                    impulse_entity,
                    ActorImpulse(
                        actor_entity_id=actor_entity,
                        turn_id=state.turn_id,
                        scene_id=state.current_location,
                        goal=goal,
                        impulse=impulse,
                        zone=position.zone,
                        distance_bucket=position.distance_bucket,
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
                            zone=position.zone,
                            distance_bucket=position.distance_bucket.value,
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
        """Register/update actor agency state from LLM payload on response turns."""
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
            inherited_flags = _get_faction_flags(world, command.faction_entity_id)
            normalized_traits = _merge_traits(
                command.faction_traits,
                inherited_flags,
            )
            scene_zone = command.scene_zone.strip() or "default"
            distance_bucket = _parse_distance_bucket(command.scene_distance_bucket)
            from_scene = _assign_actor_location(
                world=world,
                actor_entity=actor_entity,
                to_scene_id=command.scene_id,
                zone=scene_zone,
                distance_bucket=distance_bucket,
            )
            world.add_component(
                actor_entity,
                LongTermGoals(goals=command.long_term_goals),
            )
            world.add_component(
                actor_entity,
                FactionRelations(standings=sanitized_relations),
            )
            world.add_component(
                actor_entity,
                FactionTraits(traits=normalized_traits),
            )
            if command.faction_entity_id is not None:
                world.add_component(
                    actor_entity,
                    FactionMembership(faction_entity_id=command.faction_entity_id),
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
            inferred_turns_since = (
                max(0, command.turns_since_last_impulse)
                if command.turns_since_last_impulse is not None
                else _compute_default_turns_since(current_turn)
            )
            world.add_component(
                actor_entity,
                InitiativeState(
                    min_turns_between_impulses=max(
                        1, command.min_turns_between_impulses
                    ),
                    turns_since_last_impulse=inferred_turns_since,
                    last_impulse_turn=(
                        current_turn - inferred_turns_since
                        if current_turn >= 0
                        else -1
                    ),
                ),
            )
            current_action = command.current_action or impulse
            world.add_component(
                actor_entity,
                CurrentAction(
                    description=current_action,
                    source=self.name,
                    turn_id=current_turn,
                ),
            )
            _append_action_history(
                world=world,
                actor_entity=actor_entity,
                record=ActionRecord(
                    turn_id=current_turn,
                    action=current_action,
                    source=self.name,
                    note="llm_registration",
                ),
            )

            world.publish(
                ActorRegisteredEvent(
                    actor_entity_id=actor_entity,
                    actor_name=command.actor_name,
                    scene_id=command.scene_id,
                    long_term_goals=command.long_term_goals,
                    faction_relations=sanitized_relations,
                    scene_zone=scene_zone,
                    scene_distance_bucket=distance_bucket.value,
                )
            )
            if from_scene and from_scene != command.scene_id:
                world.publish(
                    ActorLocationChangedEvent(
                        actor_entity_id=actor_entity,
                        from_scene_id=from_scene,
                        to_scene_id=command.scene_id,
                        to_zone=scene_zone,
                        to_distance_bucket=distance_bucket.value,
                        source=self.name,
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
                    zone=scene_zone,
                    distance_bucket=distance_bucket.value,
                )
            )
            world.remove_component(command_entity, LLMActorRegistrationCommand)

            registered.append(
                {
                    "command_entity": command_entity,
                    "actor_entity": actor_entity,
                    "short_term_goal": short_term_goal,
                    "impulse": impulse,
                    "faction_traits": normalized_traits,
                    "current_action": current_action,
                    "scene_zone": scene_zone,
                    "scene_distance_bucket": distance_bucket.value,
                    "from_scene_id": from_scene,
                }
            )

        return SystemResult(
            self.name,
            len(entities),
            {"registered": registered},
        )


@dataclass
class LLMFactionGatewaySystem:
    """Register/update factions from LLM payload including heat/goals/clocks/flags."""

    name: str = "llm_faction_gateway"
    query: EntityQuery = EntityQuery(all_of=(LLMFactionUpdateCommand,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Apply LLM faction payloads to faction state components."""
        updated: list[dict[str, object]] = []
        for command_entity in entities:
            command = world.get_component(command_entity, LLMFactionUpdateCommand)
            faction_entity = command.faction_entity_id
            if faction_entity is None:
                faction_entity = world.create_entity()

            world.add_component(faction_entity, Faction(name=command.faction_name))
            world.add_component(
                faction_entity,
                FactionHeat(value=max(0, min(100, int(command.heat)))),
            )
            normalized_flags = _normalize_faction_traits(command.flags)
            world.add_component(faction_entity, FactionFlags(flags=normalized_flags))
            world.add_component(
                faction_entity,
                FactionGoals(
                    global_goals=command.global_goals,
                    regional_goals=dict(command.regional_goals),
                ),
            )
            world.add_component(
                faction_entity,
                GrandPlanClock(
                    name=command.grand_plan_name,
                    progress=max(0.0, float(command.grand_plan_progress)),
                    max_progress=max(1.0, float(command.grand_plan_max_progress)),
                    rate_per_turn=max(0.0, float(command.grand_plan_rate_per_turn)),
                ),
            )
            world.publish(
                FactionUpdatedEvent(
                    faction_entity_id=faction_entity,
                    faction_name=command.faction_name,
                    heat=max(0, min(100, int(command.heat))),
                    flags=normalized_flags,
                )
            )
            world.remove_component(command_entity, LLMFactionUpdateCommand)
            updated.append(
                {
                    "command_entity": command_entity,
                    "faction_entity": faction_entity,
                    "flags": normalized_flags,
                }
            )

        return SystemResult(self.name, len(entities), {"updated": updated})


@dataclass
class FactionTickSystem:
    """Advance faction grand-plan clocks using each faction's configured rate."""

    name: str = "faction_tick"
    query: EntityQuery = EntityQuery(all_of=(Faction, GrandPlanClock))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Advance each faction clock by its configured per-turn rate."""
        advanced: list[dict[str, object]] = []
        for faction_entity in entities:
            clock = world.get_component(faction_entity, GrandPlanClock)
            next_progress = min(
                clock.max_progress,
                clock.progress + clock.rate_per_turn,
            )
            world.add_component(
                faction_entity,
                replace(clock, progress=next_progress),
            )
            advanced.append(
                {
                    "faction_entity": faction_entity,
                    "progress": next_progress,
                    "max_progress": clock.max_progress,
                }
            )
        return SystemResult(self.name, len(entities), {"advanced": advanced})


@dataclass
class LLMPlayerAgencySystem:
    """Apply LLM-evaluated player agency actions and track action history."""

    name: str = "llm_player_agency"
    query: EntityQuery = EntityQuery(all_of=(LLMPlayerAgencyCommand,))

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Store LLM-selected player actions and publish action events."""
        kernels = world.query(EntityQuery(all_of=(KernelState,)))
        current_turn = (
            world.get_component(kernels[0], KernelState).turn_id if kernels else -1
        )

        applied: list[dict[str, object]] = []
        for command_entity in entities:
            command = world.get_component(command_entity, LLMPlayerAgencyCommand)
            if not world.has_component(command.player_entity_id, PlayerActor):
                world.remove_component(command_entity, LLMPlayerAgencyCommand)
                continue

            world.add_component(
                command.player_entity_id,
                CurrentAction(
                    description=command.action,
                    source=self.name,
                    turn_id=current_turn,
                ),
            )
            _append_action_history(
                world=world,
                actor_entity=command.player_entity_id,
                record=ActionRecord(
                    turn_id=current_turn,
                    action=command.action,
                    source=self.name,
                    note=command.intent,
                ),
            )
            world.publish(
                PlayerActionEvent(
                    player_entity_id=command.player_entity_id,
                    turn_id=current_turn,
                    action=command.action,
                    intent=command.intent,
                    target_entity_id=command.target_entity_id,
                    source=self.name,
                )
            )
            world.remove_component(command_entity, LLMPlayerAgencyCommand)
            applied.append(
                {
                    "command_entity": command_entity,
                    "player_entity_id": command.player_entity_id,
                    "action": command.action,
                }
            )

        return SystemResult(self.name, len(entities), {"applied": applied})


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


def _normalize_faction_traits(traits: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize and deduplicate trait labels while preserving order."""
    normalized: list[str] = []
    for trait in traits:
        cleaned = trait.strip().lower()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return tuple(normalized)


def _merge_traits(
    actor_traits: tuple[str, ...], inherited_traits: tuple[str, ...]
) -> tuple[str, ...]:
    """Merge direct and inherited traits with normalization + deduplication."""
    return _normalize_faction_traits(actor_traits + inherited_traits)


def _get_faction_flags(world: World, faction_entity_id: int | None) -> tuple[str, ...]:
    """Return faction flags when the actor points at an existing faction entity."""
    if faction_entity_id is None:
        return ()
    if not world.has_component(faction_entity_id, FactionFlags):
        return ()
    return world.get_component(faction_entity_id, FactionFlags).flags


def _append_action_history(
    world: World, actor_entity: int, record: ActionRecord
) -> None:
    """Append a record to actor history, creating it when absent."""
    if world.has_component(actor_entity, ActionHistory):
        history = world.get_component(actor_entity, ActionHistory)
        world.add_component(actor_entity, ActionHistory(history.records + (record,)))
        return
    world.add_component(actor_entity, ActionHistory(records=(record,)))


def _get_actor_scene_id(world: World, actor_entity: int) -> str:
    """Return actor current scene id, empty string when unset."""
    if not world.has_component(actor_entity, ScenePresence):
        return ""
    return world.get_component(actor_entity, ScenePresence).scene_id


def _ensure_location_entity(world: World, scene_id: str) -> int:
    """Get or create location entity for a scene id."""
    for entity in world.query(EntityQuery(all_of=(Location,))):
        location = world.get_component(entity, Location)
        if location.scene_id == scene_id:
            return entity

    entity = world.create_entity()
    world.add_component(entity, Location(scene_id=scene_id))
    world.add_component(entity, LocationOccupancy())
    return entity


def _assign_actor_location(
    world: World,
    actor_entity: int,
    to_scene_id: str,
    zone: str,
    distance_bucket: DistanceBucket,
) -> str:
    """Assign actor to destination scene and update source/destination occupancy."""
    from_scene = _get_actor_scene_id(world, actor_entity)

    if from_scene:
        from_location_entity = _ensure_location_entity(world, from_scene)
        occupancy = world.get_component(from_location_entity, LocationOccupancy)
        world.add_component(
            from_location_entity,
            LocationOccupancy(
                actor_entity_ids=tuple(
                    entity
                    for entity in occupancy.actor_entity_ids
                    if entity != actor_entity
                )
            ),
        )

    to_location_entity = _ensure_location_entity(world, to_scene_id)
    occupancy = world.get_component(to_location_entity, LocationOccupancy)
    if actor_entity not in occupancy.actor_entity_ids:
        world.add_component(
            to_location_entity,
            LocationOccupancy(
                actor_entity_ids=occupancy.actor_entity_ids + (actor_entity,)
            ),
        )

    world.add_component(actor_entity, ScenePresence(scene_id=to_scene_id))
    world.add_component(
        actor_entity,
        ScenePosition(
            scene_id=to_scene_id,
            zone=zone,
            distance_bucket=distance_bucket,
        ),
    )
    return from_scene


def _sync_kernel_location_for_player(
    world: World, actor_entity: int, to_scene_id: str
) -> None:
    """When moved actor is a player, sync kernel current location to destination."""
    if not world.has_component(actor_entity, PlayerActor):
        return
    for kernel_entity in world.query(EntityQuery(all_of=(KernelState,))):
        state = world.get_component(kernel_entity, KernelState)
        world.add_component(kernel_entity, replace(state, current_location=to_scene_id))


def _parse_distance_bucket(value: str) -> DistanceBucket:
    """Parse a string into a known distance bucket; default to ``NEAR``."""
    normalized = value.strip().lower()
    for bucket in DistanceBucket:
        if bucket.value == normalized:
            return bucket
    return DistanceBucket.NEAR


def _get_or_create_scene_position(world: World, actor_entity: int) -> ScenePosition:
    """Ensure actor has ScenePosition and keep scene_id synced with ScenePresence."""
    presence = world.get_component(actor_entity, ScenePresence)
    if world.has_component(actor_entity, ScenePosition):
        position = world.get_component(actor_entity, ScenePosition)
        if position.scene_id == presence.scene_id:
            return position
        updated = replace(position, scene_id=presence.scene_id)
        world.add_component(actor_entity, updated)
        return updated

    position = ScenePosition(scene_id=presence.scene_id)
    world.add_component(actor_entity, position)
    return position


def _get_or_create_initiative_state(world: World, actor_entity: int) -> InitiativeState:
    """Return initiative state and initialize defaults for actors that lack it."""
    if world.has_component(actor_entity, InitiativeState):
        return world.get_component(actor_entity, InitiativeState)
    default_state = InitiativeState()
    world.add_component(actor_entity, default_state)
    return default_state


def _compute_turns_since_last_impulse(turn_id: int, initiative: InitiativeState) -> int:
    """Compute elapsed turns from initiative state with sane defaults."""
    if initiative.last_impulse_turn < 0:
        return max(initiative.turns_since_last_impulse, turn_id + 1)
    return max(0, turn_id - initiative.last_impulse_turn)


def _compute_default_turns_since(current_turn: int) -> int:
    """Default elapsed turns for newly registered actors."""
    if current_turn < 0:
        return 9999
    return current_turn + 1
