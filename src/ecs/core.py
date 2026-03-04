"""Generic ECS primitives with query-oriented system support."""

from __future__ import annotations

import importlib
import os
import tempfile
import uuid
import warnings
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any, Protocol

EntityId = int


@dataclass(frozen=True)
class SystemResult:
    """A serializable response emitted by a system run."""

    system_name: str
    entities_processed: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EntityQuery:
    """Query constraints inspired by DefaultEcs entity filtering."""

    all_of: tuple[type[Any], ...] = ()
    none_of: tuple[type[Any], ...] = ()
    any_of: tuple[type[Any], ...] = ()


@dataclass
class EntitySet:
    """Cached entity list for a given query, refreshed on world changes."""

    query: EntityQuery
    _cached_version: int = -1
    _cached_entities: tuple[EntityId, ...] = ()

    def entities(self, world: World) -> tuple[EntityId, ...]:
        if self._cached_version != world._version:
            self._cached_entities = tuple(world.query(self.query))
            self._cached_version = world._version
        return self._cached_entities

    def complete(self) -> None:
        """Reset cache (mirrors DefaultEcs Complete for event-like sets)."""
        self._cached_version = -1
        self._cached_entities = ()


@dataclass(frozen=True)
class QueryBuilder:
    """Fluent query builder similar to DefaultEcs query composition."""

    all_of: tuple[type[Any], ...] = ()
    none_of: tuple[type[Any], ...] = ()
    any_of: tuple[type[Any], ...] = ()

    def with_all(self, *component_types: type[Any]) -> QueryBuilder:
        return QueryBuilder(
            all_of=self.all_of + component_types,
            none_of=self.none_of,
            any_of=self.any_of,
        )

    def without(self, *component_types: type[Any]) -> QueryBuilder:
        return QueryBuilder(
            all_of=self.all_of,
            none_of=self.none_of + component_types,
            any_of=self.any_of,
        )

    def with_any(self, *component_types: type[Any]) -> QueryBuilder:
        return QueryBuilder(
            all_of=self.all_of,
            none_of=self.none_of,
            any_of=self.any_of + component_types,
        )

    def as_query(self) -> EntityQuery:
        return EntityQuery(
            all_of=self.all_of,
            none_of=self.none_of,
            any_of=self.any_of,
        )


@dataclass
class World:
    """In-memory ECS world storing entities and components by type."""

    enable_storage: bool = True
    storage_path: str | None = None
    storage_backend: Any | None = None
    _next_entity_id: int = 1
    _components: dict[type[Any], dict[EntityId, Any]] = field(default_factory=dict)
    _version: int = 0
    _next_subscription_id: int = 1
    _subscriptions: dict[int, tuple[type[Any], Callable[[Any], None]]] = field(
        default_factory=dict
    )
    _event_queue: list[Any] = field(default_factory=list)
    _storage: Any | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.enable_storage:
            return

        if self.storage_backend is not None:
            self._storage = self.storage_backend
            self._load_from_storage()
            return

        try:
            from ttrpg_engine.world_db import WorldDB

            path = self.storage_path or os.path.join(
                tempfile.gettempdir(), f"ecs-world-{uuid.uuid4().hex}.db"
            )
            self.storage_path = path
            self._storage = WorldDB(path)
            self._load_from_storage()
        except Exception as exc:
            warnings.warn(
                f"ECS storage unavailable, falling back to in-memory only: {exc}",
                RuntimeWarning,
                stacklevel=2,
            )
            self._storage = None

    def close(self) -> None:
        """Close backing storage resources."""
        if self._storage is None:
            return
        self._storage.close()
        self._storage = None

    def create_entity(self) -> EntityId:
        entity_id = self._next_entity_id
        self._next_entity_id += 1
        return entity_id

    def add_component(self, entity_id: EntityId, component: Any) -> None:
        component_type = type(component)
        if component_type not in self._components:
            self._components[component_type] = {}
        self._components[component_type][entity_id] = component
        self._persist_component(entity_id, component)
        self._version += 1

    def get_component(self, entity_id: EntityId, component_type: type[Any]) -> Any:
        exact_component = self._components.get(component_type, {}).get(entity_id)
        if exact_component is not None:
            return exact_component

        matched_components: list[tuple[type[Any], Any]] = []
        for stored_type, entity_components in self._components.items():
            if stored_type is component_type:
                continue
            if issubclass(stored_type, component_type):
                component = entity_components.get(entity_id)
                if component is not None:
                    matched_components.append((stored_type, component))

        if not matched_components:
            raise KeyError(
                f"Entity {entity_id} is missing component {component_type.__name__}"
            )
        if len(matched_components) > 1:
            matched_names = ", ".join(
                sorted(component.__name__ for component, _ in matched_components)
            )
            raise KeyError(
                f"Entity {entity_id} has multiple components matching "
                f"{component_type.__name__}: {matched_names}"
            )
        return matched_components[0][1]

    def has_component(self, entity_id: EntityId, component_type: type[Any]) -> bool:
        if entity_id in self._components.get(component_type, {}):
            return True
        return any(
            entity_id in entity_components
            for stored_type, entity_components in self._components.items()
            if (
                stored_type is not component_type
                and issubclass(stored_type, component_type)
            )
        )

    def remove_component(self, entity_id: EntityId, component_type: type[Any]) -> bool:
        entity_components = self._components.get(component_type)
        if entity_components is None:
            return False
        if entity_id not in entity_components:
            return False
        del entity_components[entity_id]
        if not entity_components:
            del self._components[component_type]
        self._persist_component_delete(entity_id, component_type)
        self._version += 1
        return True

    def destroy_entity(self, entity_id: EntityId) -> None:
        removed_any = False
        for component_type, entity_components in list(self._components.items()):
            if entity_components.pop(entity_id, None) is not None:
                removed_any = True
                self._persist_component_delete(entity_id, component_type)
            if not entity_components:
                del self._components[component_type]
        if removed_any:
            self._version += 1

    def get_entities(self) -> QueryBuilder:
        return QueryBuilder()

    def create_entity_set(self, query: EntityQuery) -> EntitySet:
        return EntitySet(query=query)

    def query(self, entity_query: EntityQuery) -> list[EntityId]:
        if entity_query.all_of:
            entity_sets = [
                self._entities_with_component_type(component_type)
                for component_type in entity_query.all_of
            ]
            matching_entities = (
                set.intersection(*entity_sets) if entity_sets else set[EntityId]()
            )
        else:
            matching_entities = self._all_entities()

        if entity_query.any_of:
            any_entities = set().union(
                *(
                    self._entities_with_component_type(component_type)
                    for component_type in entity_query.any_of
                )
            )
            matching_entities &= any_entities

        if entity_query.none_of:
            excluded = set().union(
                *(
                    self._entities_with_component_type(component_type)
                    for component_type in entity_query.none_of
                )
            )
            matching_entities -= excluded

        return sorted(matching_entities)

    def query_entities(self, component_types: tuple[type[Any], ...]) -> list[EntityId]:
        # Backward-compatible helper for all-of queries.
        return self.query(EntityQuery(all_of=component_types))

    def subscribe(self, event_type: type[Any], handler: Callable[[Any], None]) -> int:
        """Subscribe a handler to published events matching ``event_type``."""
        subscription_id = self._next_subscription_id
        self._next_subscription_id += 1
        self._subscriptions[subscription_id] = (event_type, handler)
        return subscription_id

    def unsubscribe(self, subscription_id: int) -> bool:
        """Unregister an existing subscription and report whether it existed."""
        if subscription_id not in self._subscriptions:
            return False
        del self._subscriptions[subscription_id]
        return True

    def publish(self, event: Any) -> None:
        """Publish an event to subscribers and store it in the in-memory queue."""
        self._event_queue.append(event)
        self._persist_event(event)
        for subscribed_type, handler in self._subscriptions.values():
            if isinstance(event, subscribed_type):
                handler(event)

    def get_published_events(self, event_type: type[Any] | None = None) -> list[Any]:
        """Return queued events, optionally filtered by ``event_type``."""
        if event_type is None:
            return list(self._event_queue)
        return [event for event in self._event_queue if isinstance(event, event_type)]

    def consume_published_events(
        self, event_type: type[Any] | None = None
    ) -> list[Any]:
        """Return and remove queued events, optionally filtered by ``event_type``."""
        if event_type is None:
            events = list(self._event_queue)
            self._event_queue.clear()
            return events

        kept: list[Any] = []
        consumed: list[Any] = []
        for event in self._event_queue:
            if isinstance(event, event_type):
                consumed.append(event)
            else:
                kept.append(event)
        self._event_queue = kept
        return consumed

    def _all_entities(self) -> set[EntityId]:
        if not self._components:
            return set()
        return set().union(
            *(
                set(entity_components.keys())
                for entity_components in self._components.values()
            )
        )

    def _entities_with_component_type(self, component_type: type[Any]) -> set[EntityId]:
        entity_ids: set[EntityId] = set()
        for stored_type, entity_components in self._components.items():
            if stored_type is component_type or issubclass(stored_type, component_type):
                entity_ids.update(entity_components.keys())
        return entity_ids

    def _persist_component(self, entity_id: EntityId, component: Any) -> None:
        if self._storage is None:
            return
        component_type = type(component)
        component_type_name = _type_name(component_type)
        storage_key = _component_storage_key(entity_id, component_type_name)
        self._storage.append_only(
            {
                "id": storage_key,
                "kind": "ecs_component",
                "entity_id": entity_id,
                "component_type": component_type_name,
                "payload": _encode_value(component),
                "turn": self._version,
            }
        )

    def _persist_component_delete(
        self, entity_id: EntityId, component_type: type[Any]
    ) -> None:
        if self._storage is None:
            return
        component_type_name = _type_name(component_type)
        storage_key = _component_storage_key(entity_id, component_type_name)
        self._storage.append_only(
            {
                "id": storage_key,
                "kind": "ecs_component",
                "entity_id": entity_id,
                "component_type": component_type_name,
                "tombstone": True,
                "turn": self._version,
            }
        )

    def _persist_event(self, event: Any) -> None:
        if self._storage is None:
            return
        self._storage.append_only(
            {
                "kind": "ecs_event",
                "event_type": _type_name(type(event)),
                "payload": _encode_value(event),
                "turn": self._version,
            }
        )

    def _load_from_storage(self) -> None:
        if self._storage is None:
            return
        if not hasattr(self._storage, "iter_docs"):
            warnings.warn(
                "ECS storage backend does not support iter_docs; skipping rehydrate.",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        try:
            docs = self._storage.iter_docs(include_tombstones=True)
        except Exception:
            return

        max_entity_id = 0
        max_turn = self._version

        for doc in docs:
            if not isinstance(doc, dict):
                continue

            turn = doc.get("turn", 0)
            if isinstance(turn, int):
                max_turn = max(max_turn, turn)

            if doc.get("kind") == "ecs_event":
                payload = _decode_value(doc.get("payload"))
                self._event_queue.append(payload)
                continue

            if doc.get("kind") != "ecs_component":
                continue

            entity_value = doc.get("entity_id")
            if not isinstance(entity_value, int):
                continue
            max_entity_id = max(max_entity_id, entity_value)

            component_type_path = doc.get("component_type")
            if not isinstance(component_type_path, str):
                continue
            component_type = _load_type(component_type_path)
            if not isinstance(component_type, type):
                continue

            payload = _decode_value(doc.get("payload"))
            tombstone = bool(doc.get("tombstone"))
            if tombstone:
                entity_components = self._components.get(component_type)
                if entity_components is not None:
                    entity_components.pop(entity_value, None)
                    if not entity_components:
                        del self._components[component_type]
                continue

            if component_type not in self._components:
                self._components[component_type] = {}
            self._components[component_type][entity_value] = payload

        self._next_entity_id = max(self._next_entity_id, max_entity_id + 1)
        self._version = max(self._version, max_turn)


def _component_storage_key(entity_id: EntityId, component_type_name: str) -> str:
    return f"ecs:component:{entity_id}:{component_type_name}"


def _type_name(tp: type[Any]) -> str:
    return f"{tp.__module__}.{tp.__qualname__}"


def _encode_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return {
            "__enum__": _type_name(type(value)),
            "value": _encode_value(value.value),
        }
    if is_dataclass(value):
        return {
            "__dataclass__": _type_name(type(value)),
            "fields": {
                field_info.name: _encode_value(getattr(value, field_info.name))
                for field_info in fields(value)
            },
        }
    if isinstance(value, dict):
        return {str(key): _encode_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    if isinstance(value, tuple):
        return {
            "__tuple__": [_encode_value(item) for item in value],
        }
    return {"__repr__": repr(value)}


def _decode_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    if isinstance(value, dict):
        if "__tuple__" in value:
            raw = value["__tuple__"]
            if isinstance(raw, list):
                return tuple(_decode_value(item) for item in raw)
            return ()
        if "__enum__" in value and "value" in value:
            enum_type = _load_type(str(value["__enum__"]))
            if isinstance(enum_type, type) and issubclass(enum_type, Enum):
                return enum_type(_decode_value(value["value"]))
            return _decode_value(value["value"])
        if "__dataclass__" in value and "fields" in value:
            dataclass_type = _load_type(str(value["__dataclass__"]))
            raw_fields = value["fields"]
            if (
                isinstance(dataclass_type, type)
                and is_dataclass(dataclass_type)
                and isinstance(raw_fields, dict)
            ):
                return dataclass_type(
                    **{key: _decode_value(item) for key, item in raw_fields.items()}
                )
            if not isinstance(raw_fields, dict):
                return {}
            return {key: _decode_value(item) for key, item in raw_fields.items()}
        if "__repr__" in value:
            return value["__repr__"]
        return {str(key): _decode_value(item) for key, item in value.items()}
    return value


def _load_type(path: str) -> type[Any] | None:
    module_name, _, type_name = path.rpartition(".")
    if not module_name or not type_name:
        return None
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    candidate = getattr(module, type_name, None)
    if isinstance(candidate, type):
        return candidate
    return None


class System(Protocol):
    """Protocol every ECS system should implement."""

    name: str
    query: EntityQuery

    def run(self, world: World, entities: list[EntityId]) -> SystemResult:
        """Execute system logic and return a result payload."""


@dataclass
class GlobalSystem:
    """Runs all systems and returns one result per system."""

    systems: list[System]

    def run(self, world: World) -> list[SystemResult]:
        results: list[SystemResult] = []
        for system in self.systems:
            entities = world.query(system.query)
            results.append(system.run(world, entities))
        return results
