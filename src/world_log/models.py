from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union
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
    """Represents a political or social group within the world."""
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
        """Returns a text description of the relationship based on standing."""
        if self.standing >= 80: return "Ally"
        if self.standing >= 20: return "Friendly"
        if self.standing <= -80: return "Nemesis"
        if self.standing <= -20: return "Hostile"
        return "Neutral"

@dataclass
class AttireItem:
    """Represents a piece of clothing or equipment worn by an actor."""
    name: str
    tags: Dict[str, Any] = field(default_factory=dict)

    def __str__(self):
        if not self.tags:
            return self.name
        # Render tags nicely: "Plate Armor (condition=broken)"
        tag_str = ", ".join(f"{k}={v}" for k, v in self.tags.items())
        return f"{self.name} ({tag_str})"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mixed(cls, data: Union[str, Dict, 'AttireItem']) -> 'AttireItem':
        """Helper to normalize string/dict inputs into AttireItem objects."""
        if isinstance(data, cls): return data
        if isinstance(data, str): return cls(name=data)
        if isinstance(data, dict):
            d = data.copy()
            # Extract name/item, treat rest as tags
            name = d.pop('name', d.pop('item', 'Unknown Garment'))
            return cls(name=name, tags=d)
        return cls(name=str(data))

@dataclass
class PhysicalState:
    """Tracks the physical condition and configuration of an entity."""
    pose: str = "standing"  # e.g., standing, prone, kneeling, sitting
    mobility: str = "unrestricted"  # e.g., hobbled, crawling, grappled
    attire: List[AttireItem] = field(default_factory=lambda: [AttireItem("common clothes")])
    wounds: List[str] = field(default_factory=list)  # e.g., ["cut on left arm", "bruised eye"]
    status_effects: List[str] = field(default_factory=list)  # e.g., ["blinded", "stunned"]
    restraints: List[str] = field(default_factory=list)  # e.g., ["iron shackles", "rope bindings"]
    exposed_areas: List[str] = field(default_factory=list)  # e.g., ["left shoulder", "chest"]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PhysicalState':
        # Robustness: Handle legacy string formats if loading old data
        if 'attire' in data:
            raw = data['attire'] if isinstance(data['attire'], list) else [data['attire']]
            data['attire'] = [AttireItem.from_mixed(item) for item in raw]
            
        if 'restraints' in data and isinstance(data['restraints'], str):
            data['restraints'] = [data['restraints']] if data['restraints'] else []
            
        return cls(**data)

@dataclass
class Actor:
    """Represents a character or entity in the world."""
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
    """Represents a place in the world."""
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
    """Represents a single logged event in the world history."""
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
