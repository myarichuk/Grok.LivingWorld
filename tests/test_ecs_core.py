from __future__ import annotations

import pytest

from ecs.core import EntityQuery, GlobalSystem, SystemResult, World
from ttrpg_engine.components import ActorComponent


class Health:
    def __init__(self, current: int, maximum: int) -> None:
        self.current = current
        self.maximum = maximum


class _FakeSystem:
    name = "fake"
    query = EntityQuery(all_of=(Health,))

    def run(self, world: World, entities: list[int]) -> SystemResult:
        return SystemResult(self.name, len(entities), {"entity_ids": entities})


def test_world_creates_incrementing_entity_ids() -> None:
    world = World()

    assert world.create_entity() == 1
    assert world.create_entity() == 2


def test_world_queries_entities_by_component_intersection() -> None:
    world = World()
    entity_one = world.create_entity()
    entity_two = world.create_entity()

    world.add_component(entity_one, Health(5, 10))
    world.add_component(entity_two, Health(10, 10))

    assert world.query_entities((Health,)) == [entity_one, entity_two]


def test_world_query_supports_none_of_and_any_of_filters() -> None:
    world = World()

    class Position:
        pass

    class Hidden:
        pass

    a = world.create_entity()
    b = world.create_entity()
    c = world.create_entity()
    world.add_component(a, Health(1, 10))
    world.add_component(a, Position())
    world.add_component(b, Health(2, 10))
    world.add_component(b, Hidden())
    world.add_component(c, Position())

    query = EntityQuery(all_of=(Health,), none_of=(Hidden,), any_of=(Position,))
    assert world.query(query) == [a]


def test_query_builder_and_entity_set_cache_refresh_on_world_change() -> None:
    world = World()
    e1 = world.create_entity()
    world.add_component(e1, Health(3, 10))

    query = world.get_entities().with_all(Health).as_query()
    entity_set = world.create_entity_set(query)
    assert entity_set.entities(world) == (e1,)

    e2 = world.create_entity()
    world.add_component(e2, Health(6, 10))
    assert entity_set.entities(world) == (e1, e2)


def test_base_class_queries_match_subclass_components() -> None:
    world = World()

    class NpcActor(ActorComponent):
        def __init__(self, name: str) -> None:
            self.name = name

    actor = world.create_entity()
    world.add_component(actor, NpcActor("Rurik"))

    query = EntityQuery(all_of=(ActorComponent,))
    assert world.query(query) == [actor]
    actor_component = world.get_component(actor, ActorComponent)
    assert actor_component.name == "Rurik"


def test_get_component_raises_actionable_error_when_component_missing() -> None:
    world = World()
    entity = world.create_entity()

    with pytest.raises(KeyError, match="missing component Health"):
        world.get_component(entity, Health)


def test_remove_component_deletes_entity_component_mapping() -> None:
    world = World()
    entity = world.create_entity()
    world.add_component(entity, Health(3, 10))

    removed = world.remove_component(entity, Health)

    assert removed is True
    assert world.has_component(entity, Health) is False


def test_remove_component_polymorphic_removes_single_subclass_match() -> None:
    world = World(enable_storage=False)

    class NpcActor(ActorComponent):
        def __init__(self, name: str) -> None:
            self.name = name

    entity = world.create_entity()
    world.add_component(entity, NpcActor("Rurik"))

    removed_count = world.remove_component_polymorphic(entity, ActorComponent)

    assert removed_count == 1
    assert world.has_component(entity, ActorComponent) is False


def test_remove_component_polymorphic_raises_on_ambiguous_match() -> None:
    world = World(enable_storage=False)

    class NpcActor(ActorComponent):
        pass

    class PlayerAvatar(ActorComponent):
        pass

    entity = world.create_entity()
    world.add_component(entity, NpcActor())
    world.add_component(entity, PlayerAvatar())

    with pytest.raises(KeyError, match="multiple components matching ActorComponent"):
        world.remove_component_polymorphic(entity, ActorComponent)


def test_remove_component_polymorphic_can_remove_all_when_non_strict() -> None:
    world = World(enable_storage=False)

    class NpcActor(ActorComponent):
        pass

    class PlayerAvatar(ActorComponent):
        pass

    entity = world.create_entity()
    world.add_component(entity, NpcActor())
    world.add_component(entity, PlayerAvatar())

    removed_count = world.remove_component_polymorphic(
        entity,
        ActorComponent,
        strict_single=False,
    )

    assert removed_count == 2
    assert world.has_component(entity, ActorComponent) is False


def test_destroy_entity_removes_all_components() -> None:
    world = World()
    entity = world.create_entity()
    world.add_component(entity, Health(6, 10))

    world.destroy_entity(entity)

    assert world.has_component(entity, Health) is False


def test_global_system_runs_each_system_and_preserves_result_order() -> None:
    world = World()
    entity = world.create_entity()
    world.add_component(entity, Health(2, 10))
    system = _FakeSystem()

    results = GlobalSystem([system, system]).run(world)

    assert [result.system_name for result in results] == ["fake", "fake"]
    assert all(result.payload["entity_ids"] == [entity] for result in results)
