"""Player-related agency components."""

from __future__ import annotations

from dataclasses import dataclass

from ttrpg_engine.components.actor import ActorComponent


@dataclass(frozen=True)
class PlayerActor(ActorComponent):
    player_id: str
    display_name: str
