#!/usr/bin/env python3
"""Repair known package __init__.py files if they were uploaded as escaped blobs.

This is intentionally explicit for the package entrypoints most affected by
copy/paste/repr-style corruption.
"""

from __future__ import annotations

import pathlib

CANONICAL_INIT_FILES: dict[str, str] = {
    "src/ecs/__init__.py": '''"""Generic ECS package."""

from ecs.core import (
    EntityId,
    EntityQuery,
    EntitySet,
    GlobalSystem,
    QueryBuilder,
    SystemResult,
    World,
)

__all__ = [
    "EntityId",
    "EntityQuery",
    "EntitySet",
    "GlobalSystem",
    "QueryBuilder",
    "SystemResult",
    "World",
]
''',
    "src/ttrpg_5e/__init__.py": '''"""5e system-specific components and factories."""

from ttrpg_5e.components import (
    AbilityScores,
    Actor5e,
    CombatStats,
    SavingThrows,
    Skills,
    Spellcasting,
    SurvivalStatus,
)
from ttrpg_5e.factory import Actor5eFactory, ActorBuild5e, ActorFactory

__all__ = [
    "AbilityScores",
    "Actor5e",
    "Actor5eFactory",
    "ActorBuild5e",
    "ActorFactory",
    "CombatStats",
    "SavingThrows",
    "Skills",
    "Spellcasting",
    "SurvivalStatus",
]
''',
    "src/ttrpg_engine/components/__init__.py": '''"""TTRPG engine components."""

from ttrpg_engine.components.actor import (
    ActionHistory,
    ActionRecord,
    ActorAgency,
    ActorComponent,
    ActorImpulse,
    CurrentAction,
    FactionRelations,
    FactionTraits,
    InitiativeState,
    LongTermGoals,
    NarrativeActor,
    ScenePresence,
)
from ttrpg_engine.components.faction import (
    Faction,
    FactionFlags,
    FactionGoals,
    FactionHeat,
    FactionMembership,
    GrandPlanClock,
)
from ttrpg_engine.components.kernel import KernelState, RequestRegistry, TurnPhase
from ttrpg_engine.components.llm import (
    EndTurnCommand,
    LLMActorRegistrationCommand,
    LLMFactionUpdateCommand,
    LLMPlayerAgencyCommand,
    LLMResponse,
    NeedsLLMFill,
    ResolvedLLMResult,
    StartTurnCommand,
)
from ttrpg_engine.components.player import PlayerActor

__all__ = [
    "ActorAgency",
    "ActionHistory",
    "ActionRecord",
    "ActorComponent",
    "ActorImpulse",
    "CurrentAction",
    "EndTurnCommand",
    "Faction",
    "FactionFlags",
    "FactionGoals",
    "FactionHeat",
    "FactionMembership",
    "FactionRelations",
    "FactionTraits",
    "GrandPlanClock",
    "InitiativeState",
    "KernelState",
    "LLMActorRegistrationCommand",
    "LLMFactionUpdateCommand",
    "LLMPlayerAgencyCommand",
    "LLMResponse",
    "LongTermGoals",
    "NarrativeActor",
    "NeedsLLMFill",
    "PlayerActor",
    "RequestRegistry",
    "ResolvedLLMResult",
    "ScenePresence",
    "StartTurnCommand",
    "TurnPhase",
]
''',
    "src/ttrpg_engine/__init__.py": '''"""TTRPG kernel components and systems."""

from ttrpg_engine.components import (
    ActionHistory,
    ActionRecord,
    ActorAgency,
    ActorComponent,
    ActorImpulse,
    CurrentAction,
    EndTurnCommand,
    Faction,
    FactionFlags,
    FactionGoals,
    FactionHeat,
    FactionMembership,
    FactionRelations,
    FactionTraits,
    GrandPlanClock,
    InitiativeState,
    KernelState,
    LLMActorRegistrationCommand,
    LLMFactionUpdateCommand,
    LLMPlayerAgencyCommand,
    LLMResponse,
    LongTermGoals,
    NarrativeActor,
    NeedsLLMFill,
    PlayerActor,
    RequestRegistry,
    ResolvedLLMResult,
    ScenePresence,
    StartTurnCommand,
    TurnPhase,
)
from ttrpg_engine.events import (
    ActorImpulseEvent,
    ActorRegisteredEvent,
    FactionUpdatedEvent,
    PlayerActionEvent,
)
from ttrpg_engine.systems import (
    ActorAgencySystem,
    ApplyLLMResponseSystem,
    CommitTurnSystem,
    EndTurnSystem,
    FactionTickSystem,
    LLMActorGatewaySystem,
    LLMFactionGatewaySystem,
    LLMPlayerAgencySystem,
    StartTurnSystem,
)

__all__ = [
    "ActorAgency",
    "ActionHistory",
    "ActionRecord",
    "ActorAgencySystem",
    "ActorComponent",
    "ActorImpulse",
    "ActorImpulseEvent",
    "ActorRegisteredEvent",
    "ApplyLLMResponseSystem",
    "CommitTurnSystem",
    "CurrentAction",
    "EndTurnCommand",
    "EndTurnSystem",
    "Faction",
    "FactionFlags",
    "FactionGoals",
    "FactionHeat",
    "FactionMembership",
    "FactionRelations",
    "FactionTickSystem",
    "FactionTraits",
    "FactionUpdatedEvent",
    "GrandPlanClock",
    "InitiativeState",
    "KernelState",
    "LLMActorGatewaySystem",
    "LLMActorRegistrationCommand",
    "LLMFactionGatewaySystem",
    "LLMFactionUpdateCommand",
    "LLMPlayerAgencyCommand",
    "LLMPlayerAgencySystem",
    "LLMResponse",
    "LongTermGoals",
    "NarrativeActor",
    "NeedsLLMFill",
    "PlayerActionEvent",
    "PlayerActor",
    "RequestRegistry",
    "ResolvedLLMResult",
    "ScenePresence",
    "StartTurnCommand",
    "StartTurnSystem",
    "TurnPhase",
]
''',
}


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    for rel_path, content in CANONICAL_INIT_FILES.items():
        path = repo_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"repaired={rel_path}")
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
