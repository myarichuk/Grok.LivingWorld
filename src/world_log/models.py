from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import json

class EventType(Enum):
    DIALOGUE = "dialogue"
    ACTION = "action"
    SYSTEM = "system"
    OBSERVATION = "observation"
    SUMMARY = "summary"

@dataclass
class Faction:
    name: str
    description: str
    standing: int = 0  # Range: -100 (Nemesis) to 100 (Ally)
    active_goals: List[str] = field(default_factory=list)
    known_members: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Faction':
        return cls(**data)

    def get_relationship(self) -> str:
        if self.standing >= 80: return "Ally"
        if self.standing >= 20: return "Friendly"
        if self.standing <= -80: return "Nemesis"
        if self.standing <= -20: return "Hostile"
        return "Neutral"

@dataclass
class PhysicalState:
    """Tracks the physical condition and configuration of an entity."""
    pose: str = "standing"  # e.g., standing, prone, kneeling, sitting
    attire: str = "common clothes"
    wounds: List[str] = field(default_factory=list)  # e.g., ["cut on left arm", "bruised eye"]
    status_effects: List[str] = field(default_factory=list)  # e.g., ["blinded", "stunned"]
    restraints: Optional[str] = None  # e.g., "iron shackles", "rope bindings"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PhysicalState':
        return cls(**data)

@dataclass
class Actor:
    name: str
    description: str = ""
    state: PhysicalState = field(default_factory=PhysicalState)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Actor':
        if 'state' in data and isinstance(data['state'], dict):
            data['state'] = PhysicalState.from_dict(data['state'])
        return cls(**data)

@dataclass
class Location:
    name: str
    description: str = ""
    parent_location: Optional[str] = None
    visited: bool = False
    points_of_interest: List[str] = field(default_factory=list)
    local_history: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Location':
        return cls(**data)

@dataclass
class Event:
    id: str
    turn: int
    type: EventType
    content: str
    timestamp: datetime
    actors: List[str] = field(default_factory=list)  # List of actor names
    location: Optional[str] = None  # Location name
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    roll_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['type'] = self.type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['type'] = EventType(data['type'])
        return cls(**data)
