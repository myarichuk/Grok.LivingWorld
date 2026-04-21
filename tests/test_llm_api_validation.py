from __future__ import annotations

from ttrpg_engine.llm_api import (
    parse_llm_actor_registration_command,
    parse_llm_faction_update_command,
    parse_llm_player_agency_command,
    parse_llm_relationship_query_command,
    parse_llm_relationship_upsert_command,
    parse_llm_response,
)


def test_parse_llm_response_accepts_basic_shape() -> None:
    cmd, errors = parse_llm_response({"request_id": "r1", "payload": {"x": 1}})
    assert errors == ()
    assert cmd is not None
    assert cmd.request_id == "r1"
    assert cmd.payload == {"x": 1}


def test_parse_llm_response_rejects_non_object() -> None:
    cmd, errors = parse_llm_response(["nope"])
    assert cmd is None
    assert errors


def test_parse_llm_response_rejects_missing_request_id() -> None:
    cmd, errors = parse_llm_response({"payload": {}})
    assert cmd is None
    assert any(error.path == "request_id" for error in errors)


def test_parse_llm_response_rejects_non_object_payload() -> None:
    cmd, errors = parse_llm_response({"request_id": "r1", "payload": "nope"})
    assert cmd is None
    assert any(error.path == "payload" for error in errors)


def test_parse_llm_actor_registration_coerces_and_drops_bad_entries() -> None:
    cmd, errors = parse_llm_actor_registration_command(
        {
            "actor_name": " Kestrel ",
            "scene_id": "dock",
            "long_term_goals": ["secure route", 5, "  "],
            "faction_relations": {"city_watch": "-25", "bad": "x"},
            "min_turns_between_impulses": "2",
            "known_to_pc": "true",
            "transient_timeout_turns": "0",
        }
    )
    assert errors == ()
    assert cmd is not None
    assert cmd.actor_name == "Kestrel"
    assert cmd.long_term_goals == ("secure route", "5")
    assert cmd.faction_relations == {"city_watch": -25}
    assert cmd.min_turns_between_impulses == 2
    assert cmd.known_to_pc is True
    assert cmd.transient_timeout_turns >= 1


def test_parse_llm_actor_registration_rejects_missing_required_fields() -> None:
    cmd, errors = parse_llm_actor_registration_command({"scene_id": "dock"})
    assert cmd is None
    assert any(error.path == "actor_name" for error in errors)


def test_parse_llm_player_agency_coerces_ids_and_validates_action() -> None:
    cmd, errors = parse_llm_player_agency_command(
        {"player_entity_id": "5", "action": "open the door", "target_entity_id": "7"}
    )
    assert errors == ()
    assert cmd is not None
    assert cmd.player_entity_id == 5
    assert cmd.target_entity_id == 7


def test_parse_llm_relationship_upsert_requires_bucket_and_ids() -> None:
    cmd, errors = parse_llm_relationship_upsert_command(
        {"source_actor_entity_id": "1", "target_actor_entity_id": "2"}
    )
    assert cmd is None
    assert any(error.path == "bucket" for error in errors)


def test_parse_llm_player_agency_rejects_blank_action() -> None:
    cmd, errors = parse_llm_player_agency_command(
        {"player_entity_id": 1, "action": "   "}
    )
    assert cmd is None
    assert any(error.path == "action" for error in errors)


def test_parse_llm_faction_update_coerces_numbers_and_goals() -> None:
    cmd, errors = parse_llm_faction_update_command(
        {
            "faction_name": "Iron Fist",
            "heat": "7",
            "regional_goals": {"dock": ["extort", 1, "  "]},
            "grand_plan_progress": "12.5",
            "grand_plan_rate_per_turn": 0.25,
        }
    )
    assert errors == ()
    assert cmd is not None
    assert cmd.heat == 7
    assert cmd.regional_goals["dock"] == ("extort", "1")
    assert cmd.grand_plan_progress == 12.5
    assert cmd.grand_plan_rate_per_turn == 0.25


def test_parse_llm_relationship_query_coerces_booleans() -> None:
    cmd, errors = parse_llm_relationship_query_command(
        {
            "actor_entity_id": "5",
            "bucket": "friend",
            "include_outgoing": "false",
            "include_incoming": 0,
        }
    )
    assert errors == ()
    assert cmd is not None
    assert cmd.actor_entity_id == 5
    assert cmd.include_outgoing is False
    assert cmd.include_incoming is False


def test_parse_llm_relationship_upsert_coerces_tags_and_flags() -> None:
    cmd, errors = parse_llm_relationship_upsert_command(
        {
            "source_actor_entity_id": "1",
            "target_actor_entity_id": 2,
            "bucket": "friend",
            "score": "45",
            "tags": ["debt", 5, "  "],
            "known_to_pc": "yes",
        }
    )
    assert errors == ()
    assert cmd is not None
    assert cmd.score == 45
    assert cmd.tags == ("debt", "5")
    assert cmd.known_to_pc is True
