from __future__ import annotations

from ecs.core import EntityQuery, World
from ttrpg_5e.components import AbilityScores
from ttrpg_5e.factory import Actor5eFactory, ActorBuild5e
from ttrpg_engine.components import (
    ActionHistory,
    ActorAgency,
    ActorComponent,
    ActorImpulse,
    CurrentAction,
    DistanceBucket,
    InitiativeState,
    KernelState,
    ScenePosition,
    ScenePresence,
    TurnPhase,
)
from ttrpg_engine.systems import ActorAgencySystem


class NpcActor(ActorComponent):
    def __init__(self, name: str) -> None:
        self.name = name


def test_actor_agency_selects_two_or_three_actors_and_emits_impulses() -> None:
    world = World()
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(
            phase=TurnPhase.RESOLVING,
            turn_id=7,
            current_location="the-salty-wench",
            rng_seed=1337,
            rng_draws=0,
        ),
    )

    in_scene: list[int] = []
    for idx in range(4):
        actor = world.create_entity()
        in_scene.append(actor)
        world.add_component(actor, NpcActor(f"Actor {idx}"))
        world.add_component(actor, ScenePresence("the-salty-wench"))
        world.add_component(
            actor,
            ActorAgency(
                possible_goals=(
                    "protect allies",
                    "find weak target",
                    "search for exits",
                )
            ),
        )

    out_of_scene = world.create_entity()
    world.add_component(out_of_scene, NpcActor("Wanderer"))
    world.add_component(out_of_scene, ScenePresence("the-forest"))
    world.add_component(out_of_scene, ActorAgency(possible_goals=("flee danger",)))

    result = ActorAgencySystem().run(world, [kernel])

    processed = result.payload["processed"][0]
    selected_ids = processed["selected_actor_ids"]
    impulse_entity_ids = processed["impulse_entity_ids"]

    assert len(selected_ids) in (2, 3)
    assert all(actor_id in in_scene for actor_id in selected_ids)
    assert len(impulse_entity_ids) == len(selected_ids)

    impulse_entities = world.query(EntityQuery(all_of=(ActorImpulse,)))
    assert sorted(impulse_entities) == sorted(impulse_entity_ids)

    for actor_id in selected_ids:
        agency = world.get_component(actor_id, ActorAgency)
        assert agency.short_term_goal != ""
        assert agency.impulse != ""
        assert agency.last_impulse_turn == 7
        assert (
            world.get_component(actor_id, ScenePosition).scene_id
            == "the-salty-wench"
        )

    updated_kernel = world.get_component(kernel, KernelState)
    assert updated_kernel.rng_draws == len(selected_ids)


def test_actor_agency_queries_polymorphic_actor_implementations() -> None:
    world = World()
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(
            phase=TurnPhase.RESOLVING,
            turn_id=2,
            current_location="dockside",
            rng_seed=1337,
            rng_draws=0,
        ),
    )

    fake_actor = world.create_entity()
    world.add_component(fake_actor, NpcActor("Local Scout"))
    world.add_component(fake_actor, ScenePresence("dockside"))
    world.add_component(
        fake_actor,
        ActorAgency(possible_goals=("search for exits",)),
    )

    real_actor_component = Actor5eFactory().create_actor(
        ActorBuild5e(
            name="Aria",
            race="Human",
            class_name="Rogue",
            level=3,
            background="Criminal",
            alignment="Chaotic Good",
            max_hit_points=24,
            armor_class=15,
            speed=30,
            hit_dice="d8",
            ability_scores=AbilityScores(10, 16, 14, 12, 13, 8),
        )
    )
    real_actor = world.create_entity()
    world.add_component(real_actor, real_actor_component)
    world.add_component(real_actor, ScenePresence("dockside"))
    world.add_component(
        real_actor,
        ActorAgency(possible_goals=("protect allies",)),
    )

    result = ActorAgencySystem().run(world, [kernel])
    selected = result.payload["processed"][0]["selected_actor_ids"]

    # With two candidates the system must pick both; this proves base-class querying.
    assert selected == [fake_actor, real_actor]
    assert world.get_component(fake_actor, ActorAgency).impulse != ""
    assert world.get_component(real_actor, ActorAgency).impulse != ""


def test_actor_agency_respects_initiative_cooldown_and_tracks_current_action() -> None:
    world = World()
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(
            phase=TurnPhase.RESOLVING,
            turn_id=10,
            current_location="dockside",
            rng_seed=1337,
            rng_draws=0,
        ),
    )

    ready_actor = world.create_entity()
    world.add_component(ready_actor, NpcActor("Ready"))
    world.add_component(ready_actor, ScenePresence("dockside"))
    world.add_component(ready_actor, ActorAgency(possible_goals=("protect allies",)))
    world.add_component(
        ready_actor,
        InitiativeState(min_turns_between_impulses=2, turns_since_last_impulse=5),
    )

    cooldown_actor = world.create_entity()
    world.add_component(cooldown_actor, NpcActor("Cooling Down"))
    world.add_component(cooldown_actor, ScenePresence("dockside"))
    world.add_component(
        cooldown_actor,
        ActorAgency(possible_goals=("search for exits",)),
    )
    world.add_component(
        cooldown_actor,
        InitiativeState(
            min_turns_between_impulses=3,
            turns_since_last_impulse=1,
            last_impulse_turn=9,
        ),
    )

    result = ActorAgencySystem().run(world, [kernel])
    selected = result.payload["processed"][0]["selected_actor_ids"]

    assert selected == [ready_actor]
    assert (
        world.get_component(ready_actor, InitiativeState).turns_since_last_impulse == 0
    )
    assert (
        world.get_component(cooldown_actor, InitiativeState).turns_since_last_impulse
        == 1
    )
    assert world.get_component(ready_actor, CurrentAction).description != ""
    assert world.get_component(ready_actor, ActionHistory).records


def test_actor_agency_prioritizes_closer_distance_buckets() -> None:
    world = World()
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(
            phase=TurnPhase.RESOLVING,
            turn_id=0,
            current_location="market",
            rng_seed=1337,
            rng_draws=0,
        ),
    )

    engaged = world.create_entity()
    world.add_component(engaged, NpcActor("Engaged"))
    world.add_component(engaged, ScenePresence("market"))
    world.add_component(
        engaged,
        ScenePosition(
            scene_id="market",
            zone="square",
            distance_bucket=DistanceBucket.ENGAGED,
        ),
    )
    world.add_component(engaged, ActorAgency(possible_goals=("protect allies",)))

    close = world.create_entity()
    world.add_component(close, NpcActor("Close"))
    world.add_component(close, ScenePresence("market"))
    world.add_component(
        close,
        ScenePosition(
            scene_id="market",
            zone="square",
            distance_bucket=DistanceBucket.CLOSE,
        ),
    )
    world.add_component(close, ActorAgency(possible_goals=("search for exits",)))

    distant = world.create_entity()
    world.add_component(distant, NpcActor("Distant"))
    world.add_component(distant, ScenePresence("market"))
    world.add_component(
        distant,
        ScenePosition(
            scene_id="market",
            zone="balcony",
            distance_bucket=DistanceBucket.DISTANT,
        ),
    )
    world.add_component(distant, ActorAgency(possible_goals=("flee danger",)))

    result = ActorAgencySystem().run(world, [kernel])
    selected = result.payload["processed"][0]["selected_actor_ids"]
    assert selected == sorted([engaged, close])
