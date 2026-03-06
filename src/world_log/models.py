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
class Actor:
    name: str
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Actor':
        return cls(**data)

@dataclass
class Location:
    name: str
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Location':
        return cls(**data)

@dataclass
class Event:
    id: str
    timestamp: datetime
    type: EventType
    content: str
    actors: List[str] = field(default_factory=list)  # List of actor names
    location: Optional[str] = None  # Location name
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

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
