"""Object and environmental components for spatial awareness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Object:
    """Marker component for interactable or environmental objects."""


@dataclass(frozen=True)
class ObjectState:
    """State, physical properties, and tactical capabilities of an object."""

    name: str
    object_type: str
    state: str = "normal"
    provides_cover: bool = False
    is_interactive: bool = False


@dataclass(frozen=True)
class InteractWithObjectCommand:
    """Command to interact with an object."""

    actor_entity_id: int
    object_entity_id: int
    action: str
