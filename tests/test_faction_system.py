from __future__ import annotations

from ecs.core import World
from ttrpg_engine.components import (
    Faction,
    FactionFlags,
    FactionGoals,
    FactionHeat,
    GrandPlanClock,
    LLMFactionUpdateCommand,
)
from ttrpg_engine.events import FactionUpdatedEvent
from ttrpg_engine.systems import FactionTickSystem, LLMFactionGatewaySystem


def test_llm_faction_gateway_populates_heat_clocks_goals_and_flags() -> None:
    world = World()

    command_entity = world.create_entity()
    world.add_component(
        command_entity,
        LLMFactionUpdateCommand(
            faction_name="Iron Fist",
            heat=72,
            flags=("Violent", "Criminal"),
            global_goals=("dominate trade roads",),
            regional_goals={"riverlands": ("raid caravans",)},
            grand_plan_name="Shatter the Baronies",
            grand_plan_progress=20.0,
            grand_plan_rate_per_turn=3.5,
        ),
    )

    events: list[FactionUpdatedEvent] = []
    world.subscribe(FactionUpdatedEvent, events.append)

    result = LLMFactionGatewaySystem().run(world, [command_entity])
    faction_entity = result.payload["updated"][0]["faction_entity"]

    assert world.get_component(faction_entity, Faction).name == "Iron Fist"
    assert world.get_component(faction_entity, FactionHeat).value == 72
    assert world.get_component(faction_entity, FactionFlags).flags == (
        "violent",
        "criminal",
    )
    goals = world.get_component(faction_entity, FactionGoals)
    assert goals.global_goals == ("dominate trade roads",)
    assert goals.regional_goals == {"riverlands": ("raid caravans",)}
    clock = world.get_component(faction_entity, GrandPlanClock)
    assert clock.name == "Shatter the Baronies"
    assert clock.progress == 20.0
    assert clock.rate_per_turn == 3.5
    assert len(events) == 1


def test_faction_tick_advances_clock_progress_with_rate() -> None:
    world = World()
    faction = world.create_entity()
    world.add_component(faction, Faction(name="Iron Fist"))
    world.add_component(
        faction,
        GrandPlanClock(
            name="Shatter the Baronies",
            progress=98.0,
            max_progress=100.0,
            rate_per_turn=5.0,
        ),
    )

    result = FactionTickSystem().run(world, [faction])

    assert result.payload["advanced"][0]["progress"] == 100.0
    assert world.get_component(faction, GrandPlanClock).progress == 100.0
