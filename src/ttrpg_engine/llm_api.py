from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ttrpg_engine.components.llm import (
    LLMActorRegistrationCommand,
    LLMFactionUpdateCommand,
    LLMPlayerAgencyCommand,
    LLMRelationshipQueryCommand,
    LLMRelationshipUpsertCommand,
    LLMResponse,
)


@dataclass(frozen=True)
class LLMValidationError:
    path: str
    message: str


def parse_llm_response(data: Any) -> tuple[LLMResponse | None, tuple[LLMValidationError, ...]]:
    if not isinstance(data, dict):
        return None, (LLMValidationError(path="", message="expected object"),)
    request_id = _as_non_empty_str(data.get("request_id"), "request_id")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return None, (LLMValidationError(path="payload", message="expected object"),)
    if isinstance(request_id, LLMValidationError):
        return None, (request_id,)
    return LLMResponse(request_id=request_id, payload=payload), ()


def parse_llm_actor_registration_command(
    data: Any,
) -> tuple[LLMActorRegistrationCommand | None, tuple[LLMValidationError, ...]]:
    if not isinstance(data, dict):
        return None, (LLMValidationError(path="", message="expected object"),)

    errors: list[LLMValidationError] = []
    actor_name = _as_non_empty_str(data.get("actor_name"), "actor_name", errors)
    scene_id = _as_non_empty_str(data.get("scene_id"), "scene_id", errors)
    long_term_goals = _as_tuple_str(data.get("long_term_goals"), "long_term_goals", errors)
    faction_relations = _as_dict_str_int(
        data.get("faction_relations"), "faction_relations", errors
    )
    if errors:
        return None, tuple(errors)

    # Optional/coerced fields
    scene_zone = _as_str(data.get("scene_zone", "default")) or "default"
    scene_distance_bucket = _as_str(data.get("scene_distance_bucket", "near")) or "near"
    faction_entity_id = _as_optional_int(data.get("faction_entity_id"))
    faction_traits = _as_tuple_str(data.get("faction_traits", ()), "faction_traits")
    possible_goals = _as_tuple_str(data.get("possible_goals", ()), "possible_goals")
    actor_entity_id = _as_optional_int(data.get("actor_entity_id"))
    actor_kind = _as_str(data.get("actor_kind", "llm_npc")) or "llm_npc"
    suggested_impulse = _as_str(data.get("suggested_impulse", "")) or ""
    current_action = _as_str(data.get("current_action", "")) or ""
    turns_since_last_impulse = _as_optional_int(data.get("turns_since_last_impulse"))
    min_turns_between_impulses = _as_optional_int(data.get("min_turns_between_impulses"))
    residency_type = _as_str(data.get("residency_type", "persistent")) or "persistent"
    known_to_pc = _as_bool(data.get("known_to_pc", False))
    transient_timeout_turns = _as_optional_int(data.get("transient_timeout_turns")) or 6
    npc_tags = _as_tuple_str(data.get("npc_tags", ()), "npc_tags")
    detail_mode = _as_str(data.get("detail_mode", "full_profile")) or "full_profile"
    description = _as_str(data.get("description", "")) or ""
    notable_traits = _as_tuple_str(data.get("notable_traits", ()), "notable_traits")
    actor_tags = _as_tuple_str(data.get("actor_tags", ()), "actor_tags")

    return (
        LLMActorRegistrationCommand(
            actor_name=actor_name,
            scene_id=scene_id,
            long_term_goals=long_term_goals,
            faction_relations=faction_relations,
            scene_zone=scene_zone,
            scene_distance_bucket=scene_distance_bucket,
            faction_entity_id=faction_entity_id,
            faction_traits=faction_traits,
            possible_goals=possible_goals,
            actor_entity_id=actor_entity_id,
            actor_kind=actor_kind,
            suggested_impulse=suggested_impulse,
            current_action=current_action,
            turns_since_last_impulse=turns_since_last_impulse,
            min_turns_between_impulses=(min_turns_between_impulses or 1),
            residency_type=residency_type,
            known_to_pc=known_to_pc,
            transient_timeout_turns=max(1, transient_timeout_turns),
            npc_tags=npc_tags,
            detail_mode=detail_mode,
            description=description,
            notable_traits=notable_traits,
            actor_tags=actor_tags,
        ),
        (),
    )


def parse_llm_faction_update_command(
    data: Any,
) -> tuple[LLMFactionUpdateCommand | None, tuple[LLMValidationError, ...]]:
    if not isinstance(data, dict):
        return None, (LLMValidationError(path="", message="expected object"),)

    errors: list[LLMValidationError] = []
    faction_name = _as_non_empty_str(data.get("faction_name"), "faction_name", errors)
    if errors:
        return None, tuple(errors)

    faction_entity_id = _as_optional_int(data.get("faction_entity_id"))
    heat = _as_optional_int(data.get("heat")) or 0
    flags = _as_tuple_str(data.get("flags", ()), "flags")
    global_goals = _as_tuple_str(data.get("global_goals", ()), "global_goals")
    regional_goals = _as_dict_str_tuple_str(data.get("regional_goals", {}))

    grand_plan_name = _as_str(data.get("grand_plan_name", "grand_plan")) or "grand_plan"
    grand_plan_progress = _as_optional_float(data.get("grand_plan_progress")) or 0.0
    grand_plan_max_progress = _as_optional_float(data.get("grand_plan_max_progress")) or 100.0
    grand_plan_rate_per_turn = _as_optional_float(data.get("grand_plan_rate_per_turn")) or 1.0

    return (
        LLMFactionUpdateCommand(
            faction_name=faction_name,
            faction_entity_id=faction_entity_id,
            heat=heat,
            flags=flags,
            global_goals=global_goals,
            regional_goals=regional_goals,
            grand_plan_name=grand_plan_name,
            grand_plan_progress=grand_plan_progress,
            grand_plan_max_progress=grand_plan_max_progress,
            grand_plan_rate_per_turn=grand_plan_rate_per_turn,
        ),
        (),
    )


def parse_llm_player_agency_command(
    data: Any,
) -> tuple[LLMPlayerAgencyCommand | None, tuple[LLMValidationError, ...]]:
    if not isinstance(data, dict):
        return None, (LLMValidationError(path="", message="expected object"),)

    errors: list[LLMValidationError] = []
    player_entity_id = _as_int(data.get("player_entity_id"), "player_entity_id", errors)
    action = _as_non_empty_str(data.get("action"), "action", errors)
    if errors:
        return None, tuple(errors)

    intent = _as_str(data.get("intent", "")) or ""
    target_entity_id = _as_optional_int(data.get("target_entity_id"))

    return (
        LLMPlayerAgencyCommand(
            player_entity_id=player_entity_id,
            action=action,
            intent=intent,
            target_entity_id=target_entity_id,
        ),
        (),
    )


def parse_llm_relationship_upsert_command(
    data: Any,
) -> tuple[LLMRelationshipUpsertCommand | None, tuple[LLMValidationError, ...]]:
    if not isinstance(data, dict):
        return None, (LLMValidationError(path="", message="expected object"),)

    errors: list[LLMValidationError] = []
    source_actor_entity_id = _as_int(
        data.get("source_actor_entity_id"), "source_actor_entity_id", errors
    )
    target_actor_entity_id = _as_int(
        data.get("target_actor_entity_id"), "target_actor_entity_id", errors
    )
    bucket = _as_non_empty_str(data.get("bucket"), "bucket", errors)
    if errors:
        return None, tuple(errors)

    score = _as_optional_int(data.get("score")) or 0
    tags = _as_tuple_str(data.get("tags", ()), "tags")
    visibility = _as_str(data.get("visibility", "private")) or "private"
    known_to_pc = _as_bool(data.get("known_to_pc", False))

    return (
        LLMRelationshipUpsertCommand(
            source_actor_entity_id=source_actor_entity_id,
            target_actor_entity_id=target_actor_entity_id,
            bucket=bucket,
            score=score,
            tags=tags,
            visibility=visibility,
            known_to_pc=known_to_pc,
        ),
        (),
    )


def parse_llm_relationship_query_command(
    data: Any,
) -> tuple[LLMRelationshipQueryCommand | None, tuple[LLMValidationError, ...]]:
    if not isinstance(data, dict):
        return None, (LLMValidationError(path="", message="expected object"),)

    errors: list[LLMValidationError] = []
    actor_entity_id = _as_int(data.get("actor_entity_id"), "actor_entity_id", errors)
    if errors:
        return None, tuple(errors)

    bucket = _as_str(data.get("bucket", "")) or ""
    tag = _as_str(data.get("tag", "")) or ""
    include_outgoing = _as_bool(data.get("include_outgoing", True))
    include_incoming = _as_bool(data.get("include_incoming", True))

    return (
        LLMRelationshipQueryCommand(
            actor_entity_id=actor_entity_id,
            bucket=bucket,
            tag=tag,
            include_outgoing=include_outgoing,
            include_incoming=include_incoming,
        ),
        (),
    )


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _as_non_empty_str(
    value: Any,
    path: str,
    errors: list[LLMValidationError] | None = None,
) -> str | LLMValidationError:
    coerced = _as_str(value)
    if coerced is None or not coerced.strip():
        err = LLMValidationError(path=path, message="expected non-empty string")
        if errors is not None:
            errors.append(err)
            return ""
        return err
    return coerced.strip()


def _as_int(
    value: Any,
    path: str,
    errors: list[LLMValidationError] | None = None,
) -> int:
    coerced = _as_optional_int(value)
    if coerced is None:
        err = LLMValidationError(path=path, message="expected integer")
        if errors is not None:
            errors.append(err)
        return 0
    return coerced


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1"}:
            return True
        if normalized in {"false", "no", "n", "0"}:
            return False
    return False


def _as_tuple_str(
    value: Any,
    path: str,
    errors: list[LLMValidationError] | None = None,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        items = value
    elif isinstance(value, list):
        items = tuple(value)
    else:
        err = LLMValidationError(path=path, message="expected array of strings")
        if errors is not None:
            errors.append(err)
        return ()

    out: list[str] = []
    for idx, item in enumerate(items):
        coerced = _as_str(item)
        if coerced is None:
            err = LLMValidationError(path=f"{path}[{idx}]", message="expected string")
            if errors is not None:
                errors.append(err)
                continue
            return ()
        cleaned = coerced.strip()
        if cleaned:
            out.append(cleaned)
    return tuple(out)


def _as_dict_str_int(
    value: Any,
    path: str,
    errors: list[LLMValidationError] | None = None,
) -> dict[str, int]:
    if not isinstance(value, dict):
        err = LLMValidationError(path=path, message="expected object<string, int>")
        if errors is not None:
            errors.append(err)
        return {}

    out: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        key = _as_str(raw_key)
        number = _as_optional_int(raw_value)
        if key is None or not key.strip() or number is None:
            continue
        out[key.strip()] = number
    return out


def _as_dict_str_tuple_str(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for raw_key, raw_value in value.items():
        key = _as_str(raw_key)
        if key is None or not key.strip():
            continue
        if isinstance(raw_value, (list, tuple)):
            items = tuple(_as_str(item) for item in raw_value)
            out[key.strip()] = tuple(
                item.strip() for item in items if item is not None and item.strip()
            )
    return out
