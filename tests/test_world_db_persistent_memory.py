from __future__ import annotations

import json
from pathlib import Path

import pytest

from ecs.core import World
from ttrpg_engine.components import KernelState, TurnPhase
from ttrpg_engine.events import ActorImpulseEvent
from ttrpg_engine.world_db import WorldDB


def test_world_db_indexes_ecs_event_payload_for_search(tmp_path: Path) -> None:
    db_path = tmp_path / "ecs-world.db"
    world = World(storage_path=str(db_path))

    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.IDLE, turn_id=3, current_location="dock"),
    )
    world.publish(
        ActorImpulseEvent(
            actor_entity_id=kernel,
            target_entity_id=None,
            scene_id="dock",
            turn_id=3,
            impulse="scans the room for hidden knives",
            source="test",
        )
    )
    world.close()

    with WorldDB(str(db_path)) as db:
        rows = db.query(must=["knives"])
        assert rows
        assert any(row.get("kind") == "ecs_event" for row in rows)


def test_world_db_rebuild_counts_missing_id_lines_as_corrupt(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    db_path.write_text('{"turn":1,"text":"no id here"}\n', encoding="utf-8")

    with WorldDB(str(db_path)) as db:
        stats = db.stats()
        assert stats["doc_count"] == 0
        assert stats["corrupt_lines"] == 1


def test_world_db_skips_blank_lines(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    db_path.write_text(
        '{"id":"1","turn":1,"text":"alpha"}\n\n{"id":"2","turn":2,"text":"beta"}\n',
        encoding="utf-8",
    )
    with WorldDB(str(db_path)) as db:
        assert db.stats()["doc_count"] == 2
        assert [row["id"] for row in db.query(should=["alpha", "beta"])] == ["2", "1"]


def test_world_db_handles_invalid_compressed_doc_field_without_crashing(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "world.db"
    # Keep an id so it is stored, but make the compressed blob invalid.
    db_path.write_text(
        json.dumps({"id": "bad", "__doc_zlib_b64__": "not-base64"}) + "\n",
        encoding="utf-8",
    )
    with WorldDB(str(db_path)) as db:
        loaded = db.get("bad")
        assert loaded is not None
        assert loaded["id"] == "bad"


def test_world_db_rejects_non_json_serializable_docs(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    with WorldDB(str(db_path)) as db:
        with pytest.raises(ValueError, match="must be JSON-serializable"):
            db.append_only({"payload": {"x": object()}})


def test_world_db_advances_next_id_when_numeric_id_is_provided(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    with WorldDB(str(db_path)) as db:
        db.append_only({"id": "10", "turn": 1, "text": "manual"})
        auto_key = db.append_only({"turn": 2, "text": "auto"})
        assert auto_key == "11"
