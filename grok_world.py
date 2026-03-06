import uuid
import random
import re
from datetime import datetime
from typing import List, Dict, Optional, Any, Set
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

# --- Models ---

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

# --- Dice Utility ---

class Dice:
    """
    Utility for rolling dice. Supports standard notation (e.g., "2d6+3"),
    advantage/disadvantage, and raw rolls.
    """
    
    @staticmethod
    def roll(notation: str) -> int:
        """
        Rolls dice based on standard notation (e.g., '1d20', '2d6+4', '1d8-1').
        Returns the total result.
        """
        notation = notation.lower().replace(" ", "")
        match = re.match(r"^(\d+)d(\d+)([+-]\d+)?$", notation)
        
        if not match:
            raise ValueError(f"Invalid dice notation: {notation}")
            
        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        
        total = sum(random.randint(1, die_size) for _ in range(num_dice))
        return total + modifier

    @staticmethod
    def roll_advantage(die_size: int = 20, modifier: int = 0) -> Dict[str, Any]:
        """
        Rolls 2 dice and takes the higher value.
        Returns a dict with 'total', 'rolls', and 'modifier'.
        """
        r1 = random.randint(1, die_size)
        r2 = random.randint(1, die_size)
        kept = max(r1, r2)
        return {
            "total": kept + modifier,
            "rolls": [r1, r2],
            "kept": kept,
            "modifier": modifier,
            "type": "advantage"
        }

    @staticmethod
    def roll_disadvantage(die_size: int = 20, modifier: int = 0) -> Dict[str, Any]:
        """
        Rolls 2 dice and takes the lower value.
        Returns a dict with 'total', 'rolls', and 'modifier'.
        """
        r1 = random.randint(1, die_size)
        r2 = random.randint(1, die_size)
        kept = min(r1, r2)
        return {
            "total": kept + modifier,
            "rolls": [r1, r2],
            "kept": kept,
            "modifier": modifier,
            "type": "disadvantage"
        }
        
    @staticmethod
    def check(notation: str, dc: int) -> bool:
        """
        Performs a check against a Difficulty Class (DC).
        Returns True if roll >= DC.
        """
        return Dice.roll(notation) >= dc

# --- Storage ---

class WorldLog:
    def __init__(self):
        self.events: Dict[str, Event] = {}
        self.actors: Dict[str, Actor] = {}
        self.locations: Dict[str, Location] = {}
        
        # Indexes
        # These lists store event IDs in insertion order (chronological)
        self._events_by_actor: Dict[str, List[str]] = defaultdict(list)
        self._events_by_location: Dict[str, List[str]] = defaultdict(list)
        self._events_by_type: Dict[EventType, List[str]] = defaultdict(list)
        self._chronological_ids: List[str] = []

    def add_actor(self, name: str, description: str = "", attributes: Dict = None) -> Actor:
        if attributes is None:
            attributes = {}
        actor = Actor(name=name, description=description, attributes=attributes)
        self.actors[name] = actor
        return actor

    def get_actor(self, name: str) -> Optional[Actor]:
        return self.actors.get(name)

    def add_location(self, name: str, description: str = "", attributes: Dict = None) -> Location:
        if attributes is None:
            attributes = {}
        location = Location(name=name, description=description, attributes=attributes)
        self.locations[name] = location
        return location
    
    def get_location(self, name: str) -> Optional[Location]:
        return self.locations.get(name)

    def log_event(self, 
                  content: str, 
                  type: EventType = EventType.ACTION,
                  actors: List[str] = None, 
                  location: str = None,
                  metadata: Dict = None,
                  timestamp: datetime = None) -> Event:
        
        if actors is None:
            actors = []
        if metadata is None:
            metadata = {}
        if timestamp is None:
            timestamp = datetime.now()
            
        event_id = str(uuid.uuid4())
        
        # Auto-register actors if they don't exist
        for actor_name in actors:
            if actor_name not in self.actors:
                self.add_actor(actor_name)
        
        # Auto-register location if it doesn't exist
        if location and location not in self.locations:
            self.add_location(location)

        event = Event(
            id=event_id,
            timestamp=timestamp,
            type=type,
            content=content,
            actors=actors,
            location=location,
            metadata=metadata
        )
        
        self.events[event_id] = event
        self._chronological_ids.append(event_id)
        
        # Update indexes
        for actor_name in actors:
            self._events_by_actor[actor_name].append(event_id)
            
        if location:
            self._events_by_location[location].append(event_id)
            
        self._events_by_type[type].append(event_id)
        
        return event

    def query_events(self, 
                     actor: str = None, 
                     location: str = None, 
                     type: EventType = None,
                     limit: int = None,
                     reverse: bool = False) -> List[Event]:
        
        # Select the best index to iterate over
        # Priority: Actor -> Location -> Type -> All
        # This is a heuristic. Actor is usually more selective than Location.
        
        source_ids = []
        
        if actor:
            source_ids = self._events_by_actor.get(actor, [])
        elif location:
            source_ids = self._events_by_location.get(location, [])
        elif type:
            source_ids = self._events_by_type.get(type, [])
        else:
            source_ids = self._chronological_ids

        # Prepare iterator
        iterator = reversed(source_ids) if reverse else source_ids
        
        results = []
        count = 0
        
        for eid in iterator:
            event = self.events[eid]
            
            # Apply filters
            # Note: If we selected source_ids based on actor, we technically don't need to check actor again,
            # but checking it is cheap and safe.
            
            if actor and actor not in event.actors:
                continue
            if location and event.location != location:
                continue
            if type and event.type != type:
                continue
                
            results.append(event)
            count += 1
            
            if limit and count >= limit:
                break

        return results

    def get_context_string(self, limit: int = 10) -> str:
        """Returns a formatted string of recent events suitable for LLM context."""
        # Get recent events (reverse=True to get newest first, then limit)
        recent_events = self.query_events(limit=limit, reverse=True)
        # We want them in chronological order for the context string
        recent_events.reverse()
        
        lines = []
        for event in recent_events:
            timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            actors_str = f" [Actors: {', '.join(event.actors)}]" if event.actors else ""
            loc_str = f" [Loc: {event.location}]" if event.location else ""
            lines.append(f"[{timestamp_str}] ({event.type.value}){actors_str}{loc_str}: {event.content}")
            
        return "\n".join(lines)

# --- Bootstrap ---

def bootstrap():
    """Returns a fresh WorldLog instance ready for use."""
    return WorldLog()
