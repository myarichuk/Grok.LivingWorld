"""Actor factory abstractions for TTRPG systems."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Protocol

from ttrpg_5e.components import (
    AbilityName,
    AbilityScores,
    Actor5e,
    CombatStats,
    SavingThrows,
    SkillName,
    Skills,
    Spellcasting,
    SurvivalStatus,
)

_SKILL_TO_ABILITY: dict[SkillName, AbilityName] = {
    "acrobatics": "dexterity",
    "animal_handling": "wisdom",
    "arcana": "intelligence",
    "athletics": "strength",
    "deception": "charisma",
    "history": "intelligence",
    "insight": "wisdom",
    "intimidation": "charisma",
    "investigation": "intelligence",
    "medicine": "wisdom",
    "nature": "intelligence",
    "perception": "wisdom",
    "performance": "charisma",
    "persuasion": "charisma",
    "religion": "intelligence",
    "sleight_of_hand": "dexterity",
    "stealth": "dexterity",
    "survival": "wisdom",
}


@dataclass(frozen=True)
class ActorBuild5e:
    name: str
    race: str
    class_name: str
    level: int
    background: str
    alignment: str
    max_hit_points: int
    armor_class: int
    speed: int
    hit_dice: str
    ability_scores: AbilityScores
    proficient_skills: tuple[SkillName, ...] = ()
    proficient_saves: tuple[AbilityName, ...] = ()
    features: tuple[str, ...] = ()
    equipment: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    tool_proficiencies: tuple[str, ...] = ()
    weapon_proficiencies: tuple[str, ...] = ()
    armor_proficiencies: tuple[str, ...] = ()
    experience_points: int = 0
    inventory_item_entity_ids: tuple[int, ...] = ()
    spellcasting: Spellcasting | None = None
    body_status: SurvivalStatus = SurvivalStatus()


class ActorFactory(Protocol):
    def create_actor(self, build: object) -> object:
        """Build and return a system-specific actor record."""


class Actor5eFactory:
    """Concrete actor factory for D&D 5e records."""

    def create_actor(self, build: ActorBuild5e) -> Actor5e:
        proficiency_bonus = _proficiency_bonus_for_level(build.level)
        ability_modifiers = _ability_modifiers(build.ability_scores)

        saving_throws = SavingThrows(
            strength=_save_modifier(
                "strength", ability_modifiers, build.proficient_saves, proficiency_bonus
            ),
            dexterity=_save_modifier(
                "dexterity",
                ability_modifiers,
                build.proficient_saves,
                proficiency_bonus,
            ),
            constitution=_save_modifier(
                "constitution",
                ability_modifiers,
                build.proficient_saves,
                proficiency_bonus,
            ),
            intelligence=_save_modifier(
                "intelligence",
                ability_modifiers,
                build.proficient_saves,
                proficiency_bonus,
            ),
            wisdom=_save_modifier(
                "wisdom", ability_modifiers, build.proficient_saves, proficiency_bonus
            ),
            charisma=_save_modifier(
                "charisma", ability_modifiers, build.proficient_saves, proficiency_bonus
            ),
        )

        skills = Skills(
            **{
                skill: ability_modifiers[_SKILL_TO_ABILITY[skill]]
                + (proficiency_bonus if skill in build.proficient_skills else 0)
                for skill in _SKILL_TO_ABILITY
            }
        )

        combat = CombatStats(
            armor_class=build.armor_class,
            initiative_bonus=ability_modifiers["dexterity"],
            speed=build.speed,
            proficiency_bonus=proficiency_bonus,
            hit_dice=build.hit_dice,
        )

        return Actor5e(
            name=build.name,
            race=build.race,
            class_name=build.class_name,
            level=build.level,
            background=build.background,
            alignment=build.alignment,
            experience_points=build.experience_points,
            abilities=build.ability_scores,
            saving_throws=saving_throws,
            skills=skills,
            combat=combat,
            max_hit_points=build.max_hit_points,
            current_hit_points=build.max_hit_points,
            temporary_hit_points=0,
            hit_dice_remaining=build.level,
            death_save_successes=0,
            death_save_failures=0,
            conditions=(),
            resistances=(),
            immunities=(),
            vulnerabilities=(),
            languages=build.languages,
            skill_proficiencies=build.proficient_skills,
            save_proficiencies=build.proficient_saves,
            tool_proficiencies=build.tool_proficiencies,
            weapon_proficiencies=build.weapon_proficiencies,
            armor_proficiencies=build.armor_proficiencies,
            features=build.features,
            equipment=build.equipment,
            inventory_item_entity_ids=build.inventory_item_entity_ids,
            spellcasting=build.spellcasting,
            body_status=build.body_status,
        )


def _ability_modifiers(scores: AbilityScores) -> dict[AbilityName, int]:
    return {
        "strength": _ability_modifier(scores.strength),
        "dexterity": _ability_modifier(scores.dexterity),
        "constitution": _ability_modifier(scores.constitution),
        "intelligence": _ability_modifier(scores.intelligence),
        "wisdom": _ability_modifier(scores.wisdom),
        "charisma": _ability_modifier(scores.charisma),
    }


def _save_modifier(
    ability: AbilityName,
    ability_modifiers: dict[AbilityName, int],
    proficient_saves: tuple[AbilityName, ...],
    proficiency_bonus: int,
) -> int:
    return ability_modifiers[ability] + (
        proficiency_bonus if ability in proficient_saves else 0
    )


def _ability_modifier(score: int) -> int:
    return floor((score - 10) / 2)


def _proficiency_bonus_for_level(level: int) -> int:
    if level < 1 or level > 20:
        raise ValueError("5e level must be within 1..20")
    return 2 + ((level - 1) // 4)
