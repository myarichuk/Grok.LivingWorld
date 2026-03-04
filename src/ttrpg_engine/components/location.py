"""Location management components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """A concrete scene/location in the world graph."""

    scene_id: str
    display_name: str = ""


@dataclass(frozen=True)
class LocationOccupancy:
    """Actor entity ids currently registered at this location."""

    actor_entity_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class RegisterActorLocationCommand:
    """Register actor occupancy at a location and optional zone/distance."""

    actor_entity_id: int
    scene_id: str
    zone: str = "default"
    distance_bucket: str = "near"


@dataclass(frozen=True)
class MoveActorLocationCommand:
    """Move actor from current location to destination scene/zone/distance."""

    actor_entity_id: int
    to_scene_id: str
    to_zone: str = "default"
    to_distance_bucket: str = "near"
