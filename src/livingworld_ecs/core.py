"""Lightweight ECS primitives for LLM-oriented system outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

EntityId = int


@dataclass(frozen=True)
class SystemResult:
    """A serializable response emitted by a system run."""

    system_name: str
    entities_processed: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation for forwarding to an LLM."""
        return asdict(self)


@dataclass
class World:
    """In-memory ECS world storing entities and components by type."""

    _next_entity_id: int = 1
    _components: dict[type[Any], dict[EntityId, Any]] = field(default_factory=dict)

    def create_entity(self) -> EntityId:
        entity_id = self._next_entity_id
        self._next_entity_id += 1
        return entity_id

    def add_component(self, entity_id: EntityId, component: Any) -> None:
        component_type = type(component)
        if component_type not in self._components:
            self._components[component_type] = {}
        self._components[component_type][entity_id] = component

    def get_component(self, entity_id: EntityId, component_type: type[Any]) -> Any:
        component = self._components.get(component_type, {}).get(entity_id)
        if component is None:
            raise KeyError(
                f"Entity {entity_id} is missing component {component_type.__name__}"
            )
        return component

    def has_component(self, entity_id: EntityId, component_type: type[Any]) -> bool:
        return entity_id in self._components.get(component_type, {})

    def query_entities(self, component_types: tuple[type[Any], ...]) -> list[EntityId]:
        if not component_types:
            return []

        entity_sets = [
            set(self._components.get(component_type, {}).keys())
            for component_type in component_types
        ]
        if not entity_sets:
            return []

        matching_entities = set.intersection(*entity_sets) if entity_sets else set()
        return sorted(matching_entities)


class System(Protocol):
    """Protocol every ECS system should implement."""

    name: str
    required_components: tuple[type[Any], ...]

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Execute system logic and return a result payload."""


@dataclass
class GlobalSystem:
    """Runs all systems and returns one result per system."""

    systems: list[System]

    def run(self, world: World) -> list[SystemResult]:
        results: list[SystemResult] = []
        for system in self.systems:
            entities = world.query_entities(system.required_components)
            results.append(system.run(world, entities))
        return results
