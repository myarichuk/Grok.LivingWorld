"""D&D 5e domain components and actor records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ttrpg_engine.components import ActorComponent

AbilityName = Literal[
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
]

SkillName = Literal[
    "acrobatics",
    "animal_handling",
    "arcana",
    "athletics",
    "deception",
    "history",
    "insight",
    "intimidation",
    "investigation",
    "medicine",
    "nature",
    "perception",
    "performance",
    "persuasion",
    "religion",
    "sleight_of_hand",
    "stealth",
    "survival",
]


@dataclass(frozen=True)
class AbilityScores:
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int


@dataclass(frozen=True)
class SavingThrows:
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int


@dataclass(frozen=True)
class Skills:
    acrobatics: int
    animal_handling: int
    arcana: int
    athletics: int
    deception: int
    history: int
    insight: int
    intimidation: int
    investigation: int
    medicine: int
    nature: int
    perception: int
    performance: int
    persuasion: int
    religion: int
    sleight_of_hand: int
    stealth: int
    survival: int


@dataclass(frozen=True)
class CombatStats:
    armor_class: int
    initiative_bonus: int
    speed: int
    proficiency_bonus: int
    hit_dice: str


@dataclass(frozen=True)
class Spellcasting:
    ability: AbilityName
    spell_save_dc: int
    spell_attack_bonus: int
    spell_slots: dict[int, int]
    spells_known: tuple[str, ...]


@dataclass(frozen=True)
class SurvivalStatus:
    hunger: float = 0.0
    thirst: float = 0.0
    fatigue: float = 0.0
    temperature: float = 37.0
    infection_risk: float = 0.0


@dataclass(frozen=True)
class Actor5e(ActorComponent):
    name: str
    race: str
    class_name: str
    level: int
    background: str
    alignment: str
    experience_points: int
    abilities: AbilityScores
    saving_throws: SavingThrows
    skills: Skills
    combat: CombatStats
    max_hit_points: int
    current_hit_points: int
    temporary_hit_points: int
    hit_dice_remaining: int
    death_save_successes: int
    death_save_failures: int
    conditions: tuple[str, ...]
    resistances: tuple[str, ...]
    immunities: tuple[str, ...]
    vulnerabilities: tuple[str, ...]
    languages: tuple[str, ...]
    skill_proficiencies: tuple[SkillName, ...]
    save_proficiencies: tuple[AbilityName, ...]
    tool_proficiencies: tuple[str, ...]
    weapon_proficiencies: tuple[str, ...]
    armor_proficiencies: tuple[str, ...]
    features: tuple[str, ...]
    equipment: tuple[str, ...]
    inventory_item_entity_ids: tuple[int, ...]
    spellcasting: Spellcasting | None
    body_status: SurvivalStatus
