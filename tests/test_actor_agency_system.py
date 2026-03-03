from __future__ import annotations

from ecs.core import EntityQuery, World
from ttrpg_5e.components import AbilityScores
from ttrpg_5e.factory import Actor5eFactory, ActorBuild5e
from ttrpg_engine.components import (
    ActorAgency,
    ActorComponent,
    ActorImpulse,
    KernelState,
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
