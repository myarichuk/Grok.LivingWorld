from __future__ import annotations

from ecs.core import World
from ttrpg_engine.components import (
    ActionHistory,
    CurrentAction,
    KernelState,
    LLMPlayerAgencyCommand,
    PlayerActor,
    TurnPhase,
)
from ttrpg_engine.events import PlayerActionEvent
from ttrpg_engine.systems import LLMPlayerAgencySystem


def test_llm_player_agency_records_action_history_and_publishes_event() -> None:
    world = World()
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(phase=TurnPhase.RESOLVING, turn_id=14, current_location="dock"),
    )

    player = world.create_entity()
    world.add_component(player, PlayerActor(player_id="p1", display_name="Mira"))

    command = world.create_entity()
    world.add_component(
        command,
        LLMPlayerAgencyCommand(
            player_entity_id=player,
            action="attempts to bribe the harbor master",
            intent="gain entry to restricted docks",
            target_entity_id=99,
        ),
    )

    events: list[PlayerActionEvent] = []
    world.subscribe(PlayerActionEvent, events.append)

    result = LLMPlayerAgencySystem().run(world, [command])

    assert result.payload["applied"][0]["player_entity_id"] == player
    assert (
        world.get_component(player, CurrentAction).description
        == "attempts to bribe the harbor master"
    )
    history = world.get_component(player, ActionHistory)
    assert history.records[-1].note == "gain entry to restricted docks"
    assert len(events) == 1
    assert events[0].target_entity_id == 99
    assert events[0].turn_id == 14


def test_llm_player_agency_ignores_non_player_entity() -> None:
    world = World()
    command = world.create_entity()
    world.add_component(
        command,
        LLMPlayerAgencyCommand(
            player_entity_id=42,
            action="invalid",
        ),
    )

    result = LLMPlayerAgencySystem().run(world, [command])

    assert result.payload["applied"] == []
