from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class EventType(Enum):
    DIALOGUE = "dialogue"
    ACTION = "action"
    SYSTEM = "system"
    OBSERVATION = "observation"

@dataclass
class Actor:
    name: str
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Location:
    name: str
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Event:
    id: str
    timestamp: datetime
    type: EventType
    content: str
    actors: List[str] = field(default_factory=list)  # List of actor names
    location: Optional[str] = None  # Location name
    metadata: Dict[str, Any] = field(default_factory=dict)
