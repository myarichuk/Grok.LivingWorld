from __future__ import annotations

from pathlib import Path

from ttrpg_engine.world_db import WorldDB


def test_world_db_append_get_query_and_mmap_fetch(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"

    with WorldDB(str(db_path)) as db:
        first = db.append_only(
            {
                "turn": 1,
                "event": "Player enters The Rusty Anchor Tavern",
                "text": "smells of ale and sea salt",
            }
        )
        second = db.append_only(
            {
                "turn": 2,
                "event": "Barkeep greets",
                "text": "whatll it be stranger",
                "description": "friendly barkeep at tavern counter",
            }
        )

        assert first == "1"
        assert second == "2"

        doc = db.get("2")
        assert doc is not None
        assert doc["event"] == "Barkeep greets"

        mmap_doc = db.get_from_mmap("2")
        assert mmap_doc is not None
        assert mmap_doc["id"] == "2"

        and_results = db.query(must=["barkeep", "tavern"])
        assert [row["id"] for row in and_results] == ["2"]

        or_results = db.query(should=["ale", "barkeep"])
        assert [row["id"] for row in or_results] == ["2", "1"]


def test_world_db_query_sort_tolerates_non_numeric_turn(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    with WorldDB(str(db_path)) as db:
        db.append_only({"id": "a", "turn": "not-int", "text": "alpha marker"})
        db.append_only({"id": "b", "turn": 3, "text": "beta marker"})
        db.append_only({"id": "c", "text": "gamma marker"})

        rows = db.query(should=["marker"])
        assert [row["id"] for row in rows] == ["b", "a", "c"]


def test_world_db_persists_and_rebuilds_indexes_after_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"

    with WorldDB(str(db_path)) as db:
        db.append_only({"id": "npc-kestrel", "turn": 3, "event": "kestrel scouts"})

    with WorldDB(str(db_path)) as reopened:
        doc = reopened.get("npc-kestrel")
        assert doc is not None
        assert doc["event"] == "kestrel scouts"

        query = reopened.query(must=["kestrel"])
        assert [row["id"] for row in query] == ["npc-kestrel"]


def test_world_db_checkpoint_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    with WorldDB(str(db_path)) as db:
        db.append_only({"turn": 1, "text": "market opens"})
        db.append_only({"turn": 2, "text": "guards arrive"})
        blob = db.export_checkpoint()
        assert blob

    restored_path = tmp_path / "restored.db"
    with WorldDB(str(restored_path)) as restored:
        loaded = restored.import_checkpoint(blob)
        assert loaded == 2
        assert restored.query(must=["guards"])[0]["turn"] == 2
        assert restored.export_checkpoint() == ""


def test_world_db_soft_delete_and_compact(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"

    with WorldDB(str(db_path)) as db:
        db.append_only({"id": "npc-1", "turn": 1, "event": "arrives at dock"})
        db.append_only({"id": "npc-1", "turn": 2, "event": "moves to tavern"})
        db.append_only({"id": "npc-2", "turn": 3, "event": "guards gate"})

        assert db.delete("npc-1", turn=4) is True
        assert db.delete("npc-1") is False
        assert db.get("npc-1") is None
        assert db.get_from_mmap("npc-1") is None
        assert [row["id"] for row in db.query(should=["tavern", "guards"])] == ["npc-2"]
        assert db.stats()["tombstones"] == 1

        pre_compact_size = db.stats()["file_size_bytes"]
        persisted = db.compact()
        post_compact_size = db.stats()["file_size_bytes"]

        assert persisted == 1
        assert post_compact_size <= pre_compact_size
        assert db.get("npc-2") is not None
        assert db.get("npc-1") is None
        assert db.stats()["tombstones"] == 0

    with WorldDB(str(db_path)) as reopened:
        assert reopened.get("npc-2") is not None
        assert reopened.get("npc-1") is None


def test_world_db_compresses_large_payload_and_restores_on_read(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    with WorldDB(str(db_path)) as db:
        key = db.append_only(
            {
                "id": "big",
                "turn": 9,
                "payload": {"blob": "x" * 5000},
                "event": "large payload event",
            }
        )
        assert key == "big"
        loaded = db.get("big")
        assert loaded is not None
        assert isinstance(loaded["payload"], dict)
        assert loaded["payload"]["blob"] == "x" * 5000
        mmap_loaded = db.get_from_mmap("big")
        assert mmap_loaded is not None
        assert mmap_loaded["payload"]["blob"] == "x" * 5000

    raw = db_path.read_text(encoding="utf-8")
    assert "__payload_zlib_b64__" in raw


def test_world_db_skips_corrupt_lines(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    db_path.write_bytes(
        b'{"id":"1","turn":1,"text":"clean"}\n'
        b'{"id":"2","turn":2,"text":"still clean"}\n'
        b'{invalid json line\n'
    )

    with WorldDB(str(db_path)) as db:
        stats = db.stats()
        assert stats["doc_count"] == 2
        assert stats["corrupt_lines"] == 1
        assert db.get("1") is not None
        assert db.get("2") is not None


def test_world_db_invalid_checkpoint_returns_minus_one(tmp_path: Path) -> None:
    db_path = tmp_path / "world.db"
    with WorldDB(str(db_path)) as db:
        assert db.import_checkpoint("not-base64") == -1
