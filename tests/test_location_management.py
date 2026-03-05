from __future__ import annotations

from ecs.core import EntityQuery, World
from ttrpg_engine.components import (
    ActorComponent,
    DistanceBucket,
    KernelState,
    Location,
    LocationIndex,
    LocationOccupancy,
    MoveActorLocationCommand,
    PlayerActor,
    RegisterActorLocationCommand,
    ScenePosition,
    ScenePresence,
    TurnPhase,
)
from ttrpg_engine.events import ActorLocationChangedEvent
from ttrpg_engine.systems import ActorLocationChangeSystem, LocationRegistrationSystem


class NpcActor(ActorComponent):
    def __init__(self, name: str) -> None:
        self.name = name


def _location_entity_by_scene(world: World, scene_id: str) -> int:
    for entity in world.query(EntityQuery(all_of=(Location,))):
        if world.get_component(entity, Location).scene_id == scene_id:
            return entity
    raise AssertionError(f"missing scene {scene_id}")


def test_location_registration_creates_location_and_occupancy() -> None:
    world = World()
    actor = world.create_entity()
    world.add_component(actor, NpcActor("Rook"))

    command = world.create_entity()
    world.add_component(
        command,
        RegisterActorLocationCommand(
            actor_entity_id=actor,
            scene_id="docks",
            zone="warehouse_row",
            distance_bucket="close",
        ),
    )

    result = LocationRegistrationSystem().run(world, [command])
    assert result.payload["rejected"] == []

    docks = _location_entity_by_scene(world, "docks")
    occupancy = world.get_component(docks, LocationOccupancy)
    assert occupancy.actor_entity_ids == (actor,)
    assert world.get_component(actor, ScenePresence).scene_id == "docks"
    position = world.get_component(actor, ScenePosition)
    assert position.zone == "warehouse_row"
    assert position.distance_bucket is DistanceBucket.CLOSE
    index_entity = world.query(EntityQuery(all_of=(LocationIndex,)))[0]
    index = world.get_component(index_entity, LocationIndex)
    assert index.scene_to_entity_id["docks"] == docks


def test_actor_location_change_updates_occupancy_and_player_kernel_location() -> None:
    world = World()
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=4, current_location="docks"),
    )

    player = world.create_entity()
    world.add_component(player, PlayerActor(player_id="p1", display_name="Nyx"))
    world.add_component(player, ScenePresence(scene_id="docks"))
    world.add_component(
        player,
        ScenePosition(
            scene_id="docks",
            zone="dock_gate",
            distance_bucket=DistanceBucket.NEAR,
        ),
    )

    register = world.create_entity()
    world.add_component(
        register,
        RegisterActorLocationCommand(actor_entity_id=player, scene_id="docks"),
    )
    LocationRegistrationSystem().run(world, [register])

    events: list[ActorLocationChangedEvent] = []
    world.subscribe(ActorLocationChangedEvent, events.append)

    move = world.create_entity()
    world.add_component(
        move,
        MoveActorLocationCommand(
            actor_entity_id=player,
            to_scene_id="tavern",
            to_zone="main_hall",
            to_distance_bucket="engaged",
        ),
    )

    result = ActorLocationChangeSystem().run(world, [move])
    assert result.payload["rejected"] == []
    assert result.payload["moved"][0]["from_scene_id"] == "docks"
    assert result.payload["moved"][0]["to_scene_id"] == "tavern"

    docks = _location_entity_by_scene(world, "docks")
    tavern = _location_entity_by_scene(world, "tavern")
    assert world.get_component(docks, LocationOccupancy).actor_entity_ids == ()
    assert world.get_component(tavern, LocationOccupancy).actor_entity_ids == (player,)
    assert world.get_component(player, ScenePresence).scene_id == "tavern"

    position = world.get_component(player, ScenePosition)
    assert position.zone == "main_hall"
    assert position.distance_bucket is DistanceBucket.ENGAGED
    assert world.get_component(kernel, KernelState).current_location == "tavern"

    assert len(events) == 1
    assert events[0].from_scene_id == "docks"
    assert events[0].to_scene_id == "tavern"
    assert events[0].to_zone == "main_hall"
    assert events[0].to_distance_bucket == "engaged"

    index_entity = world.query(EntityQuery(all_of=(LocationIndex,)))[0]
    index = world.get_component(index_entity, LocationIndex)
    assert index.scene_to_entity_id["docks"] == docks
    assert index.scene_to_entity_id["tavern"] == tavern
