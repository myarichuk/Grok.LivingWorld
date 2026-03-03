from __future__ import annotations

import pytest

from livingworld_ecs.components import Health, Position
from livingworld_ecs.core import GlobalSystem, World
from livingworld_ecs.systems import HealthSummarySystem, SpatialSummarySystem


def test_health_summary_system_reports_average_and_critical_entities() -> None:
    world = World()
    healthy = world.create_entity()
    critical = world.create_entity()

    world.add_component(healthy, Health(9, 10))
    world.add_component(critical, Health(2, 10))

    result = HealthSummarySystem().run(world, [healthy, critical])

    assert result.system_name == "health_summary"
    assert result.entities_processed == 2
    assert result.payload["critical_entities"] == [critical]
    assert result.payload["average_health_ratio"] == pytest.approx(0.55)


def test_health_summary_system_handles_empty_entity_list() -> None:
    world = World()

    result = HealthSummarySystem().run(world, [])

    assert result.entities_processed == 0
    assert result.payload == {"average_health_ratio": 0.0, "critical_entities": []}


def test_spatial_summary_system_reports_centroid_and_max_distance() -> None:
    world = World()
    left = world.create_entity()
    right = world.create_entity()

    world.add_component(left, Position(-2.0, 0.0))
    world.add_component(right, Position(2.0, 0.0))

    result = SpatialSummarySystem().run(world, [left, right])

    assert result.system_name == "spatial_summary"
    assert result.payload["centroid"] == pytest.approx([0.0, 0.0])
    assert result.payload["max_distance_from_centroid"] == pytest.approx(2.0)


def test_global_system_aggregates_multiple_system_results() -> None:
    world = World()
    entity = world.create_entity()
    world.add_component(entity, Health(7, 10))
    world.add_component(entity, Position(1.0, 2.0))

    global_system = GlobalSystem([HealthSummarySystem(), SpatialSummarySystem()])
    results = global_system.run(world)

    assert [result.system_name for result in results] == [
        "health_summary",
        "spatial_summary",
    ]
    assert results[0].payload["average_health_ratio"] == pytest.approx(0.7)
    assert results[1].payload["centroid"] == pytest.approx([1.0, 2.0])
