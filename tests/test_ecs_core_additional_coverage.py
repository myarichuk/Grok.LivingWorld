from __future__ import annotations

import warnings

from ecs.core import EntityQuery, EntitySet, QueryBuilder, SystemResult, World, _decode_value


def test_system_result_to_dict_is_serializable() -> None:
    result = SystemResult("sys", 2, {"ok": True})
    assert result.to_dict() == {
        "system_name": "sys",
        "entities_processed": 2,
        "payload": {"ok": True},
    }


def test_entity_set_complete_resets_cache() -> None:
    world = World(enable_storage=False)

    class Health:
        pass

    entity = world.create_entity()
    world.add_component(entity, Health())

    query = EntityQuery(all_of=(Health,))
    entity_set = EntitySet(query=query)
    assert entity_set.entities(world) == (entity,)
    entity_set.complete()
    assert entity_set.entities(world) == (entity,)


def test_query_builder_without_and_with_any() -> None:
    world = World(enable_storage=False)

    class Health:
        pass

    class Hidden:
        pass

    class Token:
        pass

    a = world.create_entity()
    b = world.create_entity()
    world.add_component(a, Health())
    world.add_component(a, Token())
    world.add_component(b, Health())
    world.add_component(b, Hidden())

    query = (
        QueryBuilder()
        .with_all(Health)
        .without(Hidden)
        .with_any(Token)
        .as_query()
    )
    assert world.query(query) == [a]


def test_unsubscribe_returns_false_when_missing() -> None:
    world = World(enable_storage=False)
    assert world.unsubscribe(999) is False


def test_consume_published_events_filters_and_keeps_unmatched() -> None:
    world = World(enable_storage=False)

    class A:
        def __init__(self, value: int) -> None:
            self.value = value

    class B:
        def __init__(self, value: int) -> None:
            self.value = value

    world.publish(A(1))
    world.publish(B(2))
    world.publish(A(3))

    consumed = world.consume_published_events(A)
    assert [event.value for event in consumed] == [1, 3]
    remaining = world.get_published_events()
    assert len(remaining) == 1
    assert isinstance(remaining[0], B)


def test_world_warns_when_storage_backend_lacks_iter_docs() -> None:
    class StorageWithoutIterDocs:
        def append_only(self, doc: dict[str, object]) -> str:
            return "1"

        def close(self) -> None:
            return None

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        world = World(storage_backend=StorageWithoutIterDocs())
        world.close()

    assert any("does not support iter_docs" in str(w.message) for w in captured)


def test_world_ignores_storage_backend_iter_docs_errors() -> None:
    class StorageWithBrokenIterDocs:
        def append_only(self, doc: dict[str, object]) -> str:
            return "1"

        def iter_docs(self, include_tombstones: bool = False) -> list[dict[str, object]]:
            raise RuntimeError("boom")

        def close(self) -> None:
            return None

    world = World(storage_backend=StorageWithBrokenIterDocs())
    world.close()


def test_decode_value_edge_cases_are_tolerant() -> None:
    assert _decode_value({"__tuple__": "not-a-list"}) == ()
    assert _decode_value({"__enum__": "missing.EnumType", "value": "x"}) == "x"
    assert _decode_value({"__dataclass__": "missing.Type", "fields": "nope"}) == {}
    assert _decode_value({"__repr__": "<obj>"}) == "<obj>"
