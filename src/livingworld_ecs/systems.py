"""Concrete systems that emit LLM-forwardable payloads."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from livingworld_ecs.components import Health, Position
from livingworld_ecs.core import EntityId, SystemResult, World


@dataclass
class HealthSummarySystem:
    name: str = "health_summary"
    required_components: tuple[type[object], ...] = (Health,)

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        if not entities:
            payload = {"average_health_ratio": 0.0, "critical_entities": []}
            return SystemResult(self.name, 0, payload)

        ratios: list[float] = []
        critical_entities: list[int] = []
        for entity in entities:
            health = world.get_component(entity, Health)
            ratio = health.current / max(health.maximum, 1)
            ratios.append(ratio)
            if ratio < 0.3:
                critical_entities.append(entity)

        payload = {
            "average_health_ratio": float(np.mean(np.array(ratios, dtype=float))),
            "critical_entities": critical_entities,
        }
        return SystemResult(self.name, len(entities), payload)


@dataclass
class SpatialSummarySystem:
    name: str = "spatial_summary"
    required_components: tuple[type[object], ...] = (Position,)

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        if not entities:
            payload = {"centroid": [0.0, 0.0], "max_distance_from_centroid": 0.0}
            return SystemResult(self.name, 0, payload)

        points = np.array(
            [
                [
                    world.get_component(entity, Position).x,
                    world.get_component(entity, Position).y,
                ]
                for entity in entities
            ],
            dtype=float,
        )
        centroid = points.mean(axis=0)
        distances = np.linalg.norm(points - centroid, axis=1)

        payload = {
            "centroid": centroid.tolist(),
            "max_distance_from_centroid": float(distances.max()),
        }
        return SystemResult(self.name, len(entities), payload)
