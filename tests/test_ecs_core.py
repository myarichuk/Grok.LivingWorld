from __future__ import annotations

import pytest

from ecs.core import GlobalSystem, SystemResult, World


class Health:
    def __init__(self, current: int, maximum: int) -> None:
        self.current = current
        self.maximum = maximum


class _FakeSystem:
    name = "fake"
    required_components = (Health,)

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
