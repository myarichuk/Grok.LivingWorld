from __future__ import annotations

from pathlib import Path

from ecs.core import EntityQuery, World
from ttrpg_engine.components import (
    ActorComponent,
    KernelState,
    LLMPlayerAgencyCommand,
    LLMPromoteTransientNpcCommand,
    LLMQueryTransientInteractionsCommand,
    LLMRelationshipQueryCommand,
    LLMRelationshipQueryResult,
    LLMRelationshipUpsertCommand,
    LLMTransientInteractionQueryResult,
    NarrativeActor,
    NpcLifecycle,
    NpcResidencyType,
    PlayerActor,
    RelationshipBucket,
    RelationshipEdge,
    ScenePresence,
    TurnPhase,
)
from ttrpg_engine.events import (
    NpcPromotedEvent,
    TransientNpcInteractionEvent,
)
from ttrpg_engine.systems import (
    LLMPlayerAgencySystem,
    LLMPromoteTransientNpcSystem,
    LLMRelationshipQuerySystem,
    LLMRelationshipUpsertSystem,
    LLMTransientInteractionQuerySystem,
    TransientNpcCleanupSystem,
)


class NpcActor(ActorComponent):
    def __init__(self, name: str) -> None:
        self.name = name


def _seed_kernel(world: World, turn_id: int, location: str = "tavern") -> int:
    kernel = world.create_entity()
    world.add_component(
        kernel,
        KernelState(
            phase=TurnPhase.RESOLVING,
            turn_id=turn_id,
            current_location=location,
        ),
    )
    return kernel


def test_transient_cleanup_removes_actor_from_scene_after_timeout() -> None:
    world = World()
    _seed_kernel(world, turn_id=10)

    npc = world.create_entity()
    world.add_component(npc, NpcActor("Wandering Drunk"))
    world.add_component(npc, ScenePresence(scene_id="tavern"))
    world.add_component(
        npc,
        NpcLifecycle(
            residency_type=NpcResidencyType.TRANSIENT,
            spawn_turn_id=1,
            last_seen_turn_id=4,
            transient_timeout_turns=5,
            known_to_pc=False,
        ),
    )

    result = TransientNpcCleanupSystem().run(
        world, world.query(EntityQuery(all_of=(KernelState,)))
    )
    assert result.payload["cleaned"][0]["actor_entity_id"] == npc
    assert not world.has_component(npc, ScenePresence)


def test_player_interaction_with_transient_is_queryable_for_promotion() -> None:
    world = World()
    _seed_kernel(world, turn_id=14, location="dock")

    player = world.create_entity()
    world.add_component(player, PlayerActor(player_id="p1", display_name="Mira"))

    transient = world.create_entity()
    world.add_component(transient, NpcActor("Quiet Traveler"))
    world.add_component(transient, ScenePresence(scene_id="dock"))
    world.add_component(
        transient,
        NpcLifecycle(
            residency_type=NpcResidencyType.TRANSIENT,
            spawn_turn_id=10,
            last_seen_turn_id=14,
            transient_timeout_turns=3,
            known_to_pc=False,
        ),
    )

    command = world.create_entity()
    world.add_component(
        command,
        LLMPlayerAgencyCommand(
            player_entity_id=player,
            action="asks about rumors from the road",
            intent="gather leads",
            target_entity_id=transient,
        ),
    )

    events: list[TransientNpcInteractionEvent] = []
    world.subscribe(TransientNpcInteractionEvent, events.append)
    player_result = LLMPlayerAgencySystem().run(world, [command])
    assert (
        player_result.payload["transient_interactions"][0]["npc_entity_id"]
        == transient
    )
    assert len(events) == 1

    query_command = world.create_entity()
    world.add_component(
        query_command,
        LLMQueryTransientInteractionsCommand(
            pc_entity_id=player,
            scene_id="dock",
            turn_min=10,
            turn_max=20,
        ),
    )
    query_result = LLMTransientInteractionQuerySystem().run(world, [query_command])
    result_entity = query_result.payload["results"][0]["result_entity"]
    result_component = world.get_component(
        result_entity, LLMTransientInteractionQueryResult
    )
    assert result_component.candidates[0]["npc_entity_id"] == transient


def test_promote_transient_and_persist_relationship_graph(tmp_path: Path) -> None:
    db_path = tmp_path / "npc-rel.db"
    world = World(storage_path=str(db_path))
    _seed_kernel(world, turn_id=8, location="market")

    npc = world.create_entity()
    world.add_component(npc, NarrativeActor(name="Unknown Traveler", kind="llm_npc"))
    world.add_component(
        npc,
        NpcLifecycle(
            residency_type=NpcResidencyType.TRANSIENT,
            spawn_turn_id=2,
            last_seen_turn_id=8,
            transient_timeout_turns=3,
            known_to_pc=False,
        ),
    )

    promote_command = world.create_entity()
    world.add_component(
        promote_command,
        LLMPromoteTransientNpcCommand(
            actor_entity_id=npc,
            promoted_name="Rena Ambercloak",
            known_to_pc=True,
            tags_to_add=("merchant", "caravan"),
        ),
    )
    promotion_events: list[NpcPromotedEvent] = []
    world.subscribe(NpcPromotedEvent, promotion_events.append)
    promotion_result = LLMPromoteTransientNpcSystem().run(world, [promote_command])
    assert promotion_result.payload["promoted"][0]["actor_entity"] == npc
    assert len(promotion_events) == 1
    lifecycle = world.get_component(npc, NpcLifecycle)
    assert lifecycle.residency_type is NpcResidencyType.PERSISTENT
    assert world.get_component(npc, NarrativeActor).name == "Rena Ambercloak"

    player = world.create_entity()
    world.add_component(player, PlayerActor(player_id="pc", display_name="PC"))
    upsert_command = world.create_entity()
    world.add_component(
        upsert_command,
        LLMRelationshipUpsertCommand(
            source_actor_entity_id=player,
            target_actor_entity_id=npc,
            bucket="friend",
            score=45,
            tags=("debt", "safe_contact"),
            visibility="rumor",
            known_to_pc=True,
        ),
    )
    upsert_result = LLMRelationshipUpsertSystem().run(world, [upsert_command])
    edge_entity = upsert_result.payload["upserted"][0]["edge_entity"]
    edge = world.get_component(edge_entity, RelationshipEdge)
    assert edge.bucket is RelationshipBucket.FRIEND
    assert "rel_bucket:friend" in edge.query_tags
    assert "rel_tag:debt" in edge.query_tags

    query_command = world.create_entity()
    world.add_component(
        query_command,
        LLMRelationshipQueryCommand(actor_entity_id=player, tag="debt"),
    )
    relationship_query_result = LLMRelationshipQuerySystem().run(world, [query_command])
    relationship_result_entity = relationship_query_result.payload["results"][0][
        "result_entity"
    ]
    graph_result = world.get_component(
        relationship_result_entity, LLMRelationshipQueryResult
    )
    assert graph_result.edges[0]["target_actor_entity_id"] == npc

    world.close()

    world_reloaded = World(storage_path=str(db_path))
    reloaded_edges = world_reloaded.query(EntityQuery(all_of=(RelationshipEdge,)))
    assert len(reloaded_edges) == 1
    reloaded_npc_lifecycle = world_reloaded.get_component(npc, NpcLifecycle)
    assert str(reloaded_npc_lifecycle.residency_type) == "persistent"
    world_reloaded.close()
