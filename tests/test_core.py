from __future__ import annotations

import pytest

from livingworld_ecs.components import Health
from livingworld_ecs.core import GlobalSystem, SystemResult, World


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


def test_global_system_runs_each_system_and_preserves_result_order() -> None:
    world = World()
    entity = world.create_entity()
    world.add_component(entity, Health(2, 10))
    system = _FakeSystem()

    results = GlobalSystem([system, system]).run(world)

    assert [result.system_name for result in results] == ["fake", "fake"]
    assert all(result.payload["entity_ids"] == [entity] for result in results)
