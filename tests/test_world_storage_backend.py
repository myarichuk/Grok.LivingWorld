from __future__ import annotations

import sys
import types
from pathlib import Path

from ecs.core import World
from ttrpg_engine.components import KernelState, TurnPhase
from ttrpg_engine.events import ActorImpulseEvent
from ttrpg_engine.world_db import WorldDB


def test_world_persists_component_and_event_to_world_db(tmp_path: Path) -> None:
    db_path = tmp_path / "ecs-world.db"
    world = World(storage_path=str(db_path))

    entity = world.create_entity()
    world.add_component(
        entity,
        KernelState(phase=TurnPhase.IDLE, turn_id=3, current_location="dock"),
    )

    component_key = (
        "ecs:component:"
        f"{entity}:ttrpg_engine.components.kernel.KernelState"
    )

    with WorldDB(str(db_path)) as db:
        stored_component = db.get(component_key)
        assert stored_component is not None
        assert stored_component["kind"] == "ecs_component"
        assert stored_component["entity_id"] == entity

    world.publish(
        ActorImpulseEvent(
            actor_entity_id=entity,
            target_entity_id=None,
            scene_id="dock",
            turn_id=3,
            impulse="scans the room",
            source="test",
        )
    )

    with WorldDB(str(db_path)) as db:
        event_docs = [doc for doc in db.iter_docs() if doc.get("kind") == "ecs_event"]
        assert len(event_docs) == 1
        assert (
            event_docs[0]["event_type"]
            == "ttrpg_engine.events.ActorImpulseEvent"
        )

    world.remove_component(entity, KernelState)
    with WorldDB(str(db_path)) as db:
        assert db.get(component_key) is None
        assert db.stats()["tombstones"] >= 1

    world.close()


def test_world_can_disable_storage(tmp_path: Path) -> None:
    db_path = tmp_path / "disabled.db"
    world = World(enable_storage=False, storage_path=str(db_path))

    entity = world.create_entity()
    world.add_component(entity, KernelState())

    assert not db_path.exists()
    world.close()


def test_world_rehydrates_state_from_world_db(tmp_path: Path) -> None:
    db_path = tmp_path / "rehydrate.db"

    world_a = World(storage_path=str(db_path))
    entity = world_a.create_entity()
    world_a.add_component(
        entity,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=8, current_location="market"),
    )
    world_a.publish(
        ActorImpulseEvent(
            actor_entity_id=entity,
            target_entity_id=None,
            scene_id="market",
            turn_id=8,
            impulse="keeps watch",
            source="test",
        )
    )
    world_a.close()

    world_b = World(storage_path=str(db_path))
    assert world_b.query_entities((KernelState,)) == [entity]
    loaded_state = world_b.get_component(entity, KernelState)
    assert loaded_state.turn_id == 8
    assert loaded_state.current_location == "market"
    loaded_events = world_b.get_published_events()
    assert len(loaded_events) == 1
    assert isinstance(loaded_events[0], ActorImpulseEvent)
    world_b.close()


def test_world_defaults_to_unified_runtime_world_db(
    tmp_path: Path, monkeypatch
) -> None:
    runtime_path = tmp_path / "grok_unified_engine.py"
    runtime_path.write_text("# runtime placeholder\n", encoding="utf-8")
    runtime_module = types.ModuleType("grok_unified_engine")
    runtime_module.__file__ = str(runtime_path)
    monkeypatch.setitem(sys.modules, "grok_unified_engine", runtime_module)

    world = World()
    assert world.storage_path == str(tmp_path / "world.ecs.db")
    world.close()


def test_world_reuses_existing_unified_runtime_world_db(
    tmp_path: Path, monkeypatch
) -> None:
    runtime_path = tmp_path / "grok_unified_engine.py"
    runtime_path.write_text("# runtime placeholder\n", encoding="utf-8")
    (tmp_path / "world.ecs.db").touch()
    runtime_module = types.ModuleType("grok_unified_engine")
    runtime_module.__file__ = str(runtime_path)
    monkeypatch.setitem(sys.modules, "grok_unified_engine", runtime_module)

    world = World()
    assert world.storage_path == str(tmp_path / "world.ecs.db")
    world.close()


class _MockStorage:
    def __init__(self) -> None:
        self.docs: list[dict[str, object]] = []
        self.closed = False

    def append_only(self, doc: dict[str, object]) -> str:
        record = dict(doc)
        if "id" not in record:
            record["id"] = str(len(self.docs) + 1)
        self.docs.append(record)
        return str(record["id"])

    def iter_docs(self, include_tombstones: bool = False) -> list[dict[str, object]]:
        return list(self.docs)

    def close(self) -> None:
        self.closed = True


def test_world_accepts_mock_storage_backend_for_unit_tests() -> None:
    storage = _MockStorage()
    world = World(storage_backend=storage)

    entity = world.create_entity()
    world.add_component(entity, KernelState())
    world.publish(
        ActorImpulseEvent(
            actor_entity_id=entity,
            target_entity_id=None,
            scene_id="dock",
            turn_id=0,
            impulse="waits",
            source="mock",
        )
    )

    component_docs = [doc for doc in storage.docs if doc.get("kind") == "ecs_component"]
    event_docs = [doc for doc in storage.docs if doc.get("kind") == "ecs_event"]
    assert component_docs
    assert event_docs

    world.close()
    assert storage.closed is True
