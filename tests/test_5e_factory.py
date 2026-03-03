from __future__ import annotations

import pytest

from ttrpg_5e.components import AbilityScores
from ttrpg_5e.factory import Actor5eFactory, ActorBuild5e


def test_actor_5e_factory_builds_full_record_with_modifiers() -> None:
    build = ActorBuild5e(
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
        proficient_skills=("stealth", "acrobatics", "deception"),
        proficient_saves=("dexterity", "intelligence"),
        features=("Sneak Attack",),
        equipment=("Dagger",),
        languages=("Common", "Thieves' Cant"),
    )

    actor = Actor5eFactory().create_actor(build)

    assert actor.name == "Aria"
    assert actor.combat.proficiency_bonus == 2
    assert actor.saving_throws.dexterity == 5
    assert actor.saving_throws.intelligence == 3
    assert actor.skills.stealth == 5
    assert actor.skills.acrobatics == 5
    assert actor.skills.deception == 1
    assert actor.current_hit_points == actor.max_hit_points == 24
    assert actor.hit_dice_remaining == 3


def test_actor_5e_factory_validates_level_range() -> None:
    build = ActorBuild5e(
        name="Invalid",
        race="Human",
        class_name="Fighter",
        level=0,
        background="Soldier",
        alignment="Lawful Neutral",
        max_hit_points=10,
        armor_class=16,
        speed=30,
        hit_dice="d10",
        ability_scores=AbilityScores(15, 10, 14, 8, 10, 10),
    )

    with pytest.raises(ValueError, match="level must be within 1..20"):
        Actor5eFactory().create_actor(build)
