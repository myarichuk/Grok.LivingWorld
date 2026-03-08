import uuid
import random
import re
import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Set, Union
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum

# --- models.py ---

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

# --- dice.py ---

class Dice:
    """
    Utility for rolling dice. Supports standard notation (e.g., "2d6+3"),
    advantage/disadvantage, and raw rolls.
    """
    
    MAX_DICE = 100  # Safety limit to prevent execution hangs
    
    @staticmethod
    def roll(notation: str) -> Dict[str, Any]:
        """
        Rolls dice based on standard notation (e.g., '1d20', '2d6+4', '1d8-1').
        Returns a dictionary with details for narrative generation.
        """
        notation = notation.lower().replace(" ", "")
        # Updated regex to allow 'd20' (implicit 1) and optional modifiers
        match = re.match(r"^(\d+)?d(\d+)([+-]\d+)?$", notation)
        
        if not match:
            raise ValueError(f"Invalid dice notation: {notation}")
            
        num_dice = int(match.group(1)) if match.group(1) else 1
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        
        if num_dice > Dice.MAX_DICE:
            raise ValueError(f"Too many dice: {num_dice}. Max is {Dice.MAX_DICE}.")

        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        total = sum(rolls) + modifier
        
        return {
            "total": total,
            "rolls": rolls,
            "modifier": modifier,
            "die_size": die_size,
            "type": "normal",
            "is_crit": die_size == 20 and 20 in rolls and num_dice == 1,
            "is_fumble": die_size == 20 and 1 in rolls and num_dice == 1
        }

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
            "die_size": die_size,
            "type": "advantage",
            "is_crit": die_size == 20 and kept == 20,
            "is_fumble": die_size == 20 and kept == 1
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
            "die_size": die_size,
            "type": "disadvantage",
            "is_crit": die_size == 20 and kept == 20,
            "is_fumble": die_size == 20 and kept == 1
        }
        
    @staticmethod
    def check(notation: str, dc: int) -> bool:
        """
        Performs a check against a Difficulty Class (DC).
        Returns True if roll >= DC.
        """
        return Dice.roll(notation)["total"] >= dc

# --- storage.py ---


class WorldLog:
    def __init__(self):
        self.events: Dict[str, Event] = {}
        self.actors: Dict[str, Actor] = {}
        self.locations: Dict[str, Location] = {}
        self.factions: Dict[str, Faction] = {}
        self.current_location_name: Optional[str] = None
        self.turn_count: int = 0
        
        # Indexes
        # These lists store event IDs in insertion order (chronological)
        self._events_by_actor: Dict[str, List[str]] = defaultdict(list)
        self._events_by_location: Dict[str, List[str]] = defaultdict(list)
        self._events_by_type: Dict[EventType, List[str]] = defaultdict(list)
        self._events_by_tag: Dict[str, List[str]] = defaultdict(list)
        self._chronological_ids: List[str] = []

    def add_actor(self, name: str, description: str = "", attributes: Dict = None) -> Actor:
        if attributes is None:
            attributes = {}
        actor = Actor(name=name, description=description, attributes=attributes)
        self.actors[name] = actor
        return actor

    def get_actor(self, name: str) -> Optional[Actor]:
        return self.actors.get(name)

    def get_or_create_faction(self, name: str, description: str = "Unknown") -> Faction:
        if name not in self.factions:
            self.factions[name] = Faction(name, description)
        return self.factions[name]

    def adjust_faction_standing(self, faction_name: str, amount: int) -> int:
        faction = self.get_or_create_faction(faction_name)
        faction.standing = max(-100, min(100, faction.standing + amount))
        return faction.standing

    def enter_location(self, name: str, description: str = "", parent: str = None) -> Location:
        """Moves the party to a location, creating it if it doesn't exist."""
        if name not in self.locations:
            self.locations[name] = Location(name, description, parent)
        
        loc = self.locations[name]
        # Update description if provided and previously empty
        if description and not loc.description:
            loc.description = description
            
        self.current_location_name = name
        
        if not loc.visited:
            loc.visited = True
            self.log_event(f"Party discovered {name}.", type=EventType.SYSTEM, location=name)
        else:
            self.log_event(f"Party returned to {name}.", type=EventType.SYSTEM, location=name)
            
        return loc
    
    def get_location(self, name: str) -> Optional[Location]:
        return self.locations.get(name)

    def log_event(self, 
                  content: str, 
                  type: EventType = EventType.ACTION,
                  actors: List[str] = None, 
                  location: str = None,
                  metadata: Dict = None,
                  tags: List[str] = None,
                  roll_data: Dict = None,
                  timestamp: datetime = None) -> Event:
        
        if actors is None:
            actors = []
        if metadata is None:
            metadata = {}
        if tags is None:
            tags = []
        if timestamp is None:
            timestamp = datetime.now()
        
        # Increment turn
        self.turn_count += 1
        
        # Default to current location if not specified
        if location is None and self.current_location_name:
            location = self.current_location_name
            
        event_id = str(uuid.uuid4())
        
        # Auto-register actors if they don't exist
        for actor_name in actors:
            if actor_name not in self.actors:
                self.add_actor(actor_name)
        
        # Auto-register location if it doesn't exist
        if location and location not in self.locations:
            self.locations[location] = Location(name=location)
            
        # Update location history
        if location:
            self.locations[location].local_history.append(f"[Turn {self.turn_count}] {content}")

        event = Event(
            id=event_id,
            turn=self.turn_count,
            timestamp=timestamp,
            type=type,
            content=content,
            actors=actors,
            location=location,
            metadata=metadata,
            tags=tags,
            roll_data=roll_data
        )
        
        self.events[event_id] = event
        self._chronological_ids.append(event_id)
        
        # Update indexes
        for actor_name in actors:
            self._events_by_actor[actor_name].append(event_id)
            
        if location:
            self._events_by_location[location].append(event_id)
            
        self._events_by_type[type].append(event_id)
        
        for tag in tags:
            self._events_by_tag[tag].append(event_id)
        
        return event

    def log_roll(self, actor: str, description: str, roll_dict: dict):
        """Specialized logger for dice rolls."""
        tags = ["roll"]
        if roll_dict.get("is_crit"): tags.append("crit")
        if roll_dict.get("is_fumble"): tags.append("fumble")
        
        content = f"{actor} rolled {description}: {roll_dict['total']} (Dice: {roll_dict['rolls']})"
        if "kept" in roll_dict:
            content += f" kept {roll_dict['kept']} ({roll_dict['type']})"
            
        # Add modifier info if relevant
        if roll_dict.get("modifier", 0) != 0:
            content += f" [{roll_dict['modifier']:+}]"
            
        self.log_event(content, type=EventType.SYSTEM, actors=[actor], tags=tags, roll_data=roll_dict)

    def update_actor_state(self, actor_name: str, updates: Dict[str, Any], reason: str = None) -> Optional[Event]:
        """
        Updates the physical state of an actor and logs the change.
        Example: world.update_actor_state("Bob", {"pose": "prone", "wounds": ["arrow in knee"]})
        """
        actor = self.get_actor(actor_name)
        if not actor:
            actor = self.add_actor(actor_name)
        
        changes = []
        for key, value in updates.items():
            if hasattr(actor.state, key):
                old_val = getattr(actor.state, key)
                # Only log if there is an actual change
                if old_val != value:
                    setattr(actor.state, key, value)
                    changes.append(f"{key}: {old_val} -> {value}")
            else:
                # We could raise an error here, but for resilience we'll ignore invalid keys
                pass
        
        if changes:
            content = f"State update for {actor_name}: {', '.join(changes)}"
            if reason:
                content += f" ({reason})"
            return self.log_event(content, type=EventType.SYSTEM, actors=[actor_name], tags=["state_change"])
        return None

    def query_events(self, 
                     actors: Union[str, List[str]] = None, 
                     location: str = None, 
                     type: EventType = None,
                     tags: Union[str, List[str]] = None,
                     limit: int = None,
                     reverse: bool = False) -> List[Event]:
        
        # Normalize inputs to lists
        if isinstance(actors, str):
            actors = [actors]
        if isinstance(tags, str):
            tags = [tags]

        # Start with all events
        candidate_ids = self._chronological_ids
        
        # Filter by actors (AND logic: must contain ALL specified actors)
        if actors:
            for actor in actors:
                actor_ids = set(self._events_by_actor.get(actor, []))
                candidate_ids = [eid for eid in candidate_ids if eid in actor_ids]
        
        # Filter by location
        if location:
            loc_ids = set(self._events_by_location.get(location, []))
            candidate_ids = [eid for eid in candidate_ids if eid in loc_ids]
            
        # Filter by type
        if type:
            type_ids = set(self._events_by_type.get(type, []))
            candidate_ids = [eid for eid in candidate_ids if eid in type_ids]
            
        # Filter by tags (AND logic)
        if tags:
            for tag in tags:
                tag_ids = set(self._events_by_tag.get(tag, []))
                candidate_ids = [eid for eid in candidate_ids if eid in tag_ids]

        # Retrieve event objects
        results = [self.events[eid] for eid in candidate_ids]
        
        # Sort by timestamp
        results.sort(key=lambda e: e.timestamp)
        
        if reverse:
            results.reverse()
            
        if limit:
            results = results[:limit]
            
        return results

    def get_context_summary(self, event_limit: int = 10) -> str:
        """
        Generates a rich, token-efficient context summary for the LLM.
        Includes: Current Location, Faction Standings, and Recent Log.
        """
        lines = ["=== WORLD STATE ==="]
        lines.append(f"Turn: {self.turn_count}")
        
        # 1. Location Context
        if self.current_location_name:
            loc = self.locations[self.current_location_name]
            lines.append(f"Current Location: {loc.name}")
            if loc.description:
                lines.append(f"Description: {loc.description}")
        
        # 2. Faction Context (Only show non-neutral or active)
        active_factions = [f for f in self.factions.values() if f.standing != 0]
        if active_factions:
            lines.append("\n=== FACTIONS ===")
            for f in active_factions:
                lines.append(f"{f.name}: {f.get_relationship()} ({f.standing})")

        # 3. Recent Events
        lines.append("\n=== RECENT LOG ===")
        recent_events = self.query_events(limit=event_limit, reverse=True)
        recent_events.reverse()
        
        for event in recent_events:
            # Compact format: [Turn X] Content (Location)
            loc_suffix = f" ({event.location})" if event.location and event.location != self.current_location_name else ""
            lines.append(f"[Turn {event.turn}] {event.content}{loc_suffix}")
            
        return "\n".join(lines)

    def to_json(self) -> str:
        """Serializes the entire world state to a JSON string."""
        data = {
            "events": [event.to_dict() for event in self.events.values()],
            "actors": [actor.to_dict() for actor in self.actors.values()],
            "locations": [location.to_dict() for location in self.locations.values()],
            "factions": [faction.to_dict() for faction in self.factions.values()],
            "current_location": self.current_location_name,
            "turn_count": self.turn_count
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'WorldLog':
        """Deserializes a WorldLog from a JSON string."""
        data = json.loads(json_str)
        world = cls()
        world.current_location_name = data.get("current_location")
        world.turn_count = data.get("turn_count", 0)
        
        for actor_data in data.get("actors", []):
            actor = Actor.from_dict(actor_data)
            world.actors[actor.name] = actor
            
        for loc_data in data.get("locations", []):
            loc = Location.from_dict(loc_data)
            world.locations[loc.name] = loc
            
        for fac_data in data.get("factions", []):
            fac = Faction.from_dict(fac_data)
            world.factions[fac.name] = fac
            
        # Reconstruct events and indexes
        # We need to sort events by timestamp to ensure chronological order in _chronological_ids
        events_data = data.get("events", [])
        temp_events = []
        for event_data in events_data:
            temp_events.append(Event.from_dict(event_data))
            
        temp_events.sort(key=lambda e: e.timestamp)
        
        for event in temp_events:
            world.events[event.id] = event
            world._chronological_ids.append(event.id)
            
            # Rebuild indexes
            for actor_name in event.actors:
                world._events_by_actor[actor_name].append(event.id)
            if event.location:
                world._events_by_location[event.location].append(event.id)
            world._events_by_type[event.type].append(event.id)
            for tag in event.tags:
                world._events_by_tag[tag].append(event.id)
                
        return world

    def prune_events(self, keep_last: int = 100) -> List[Event]:
        """
        Removes older events, keeping only the most recent `keep_last`.
        Returns the list of pruned events (useful for summarization).
        """
        if len(self._chronological_ids) <= keep_last:
            return []
            
        num_to_prune = len(self._chronological_ids) - keep_last
        pruned_ids = self._chronological_ids[:num_to_prune]
        kept_ids = self._chronological_ids[num_to_prune:]
        
        pruned_events = []
        
        for eid in pruned_ids:
            event = self.events.pop(eid)
            pruned_events.append(event)
            
            # Clean up indexes
            for actor in event.actors:
                if eid in self._events_by_actor[actor]:
                    self._events_by_actor[actor].remove(eid)
            if event.location:
                if eid in self._events_by_location[event.location]:
                    self._events_by_location[event.location].remove(eid)
            if eid in self._events_by_type[event.type]:
                self._events_by_type[event.type].remove(eid)
            for tag in event.tags:
                if eid in self._events_by_tag[tag]:
                    self._events_by_tag[tag].remove(eid)
                    
        self._chronological_ids = kept_ids 
        return pruned_events

    def summarize_pruned_events(self, summary_content: str, pruned_events: List[Event]):
        """
        Adds a summary event representing the pruned events.
        """
        if not pruned_events:
            return

        # Collect all unique actors and locations from pruned events to tag the summary
        all_actors = set()
        all_locations = set()
        
        for event in pruned_events:
            all_actors.update(event.actors)
            if event.location:
                all_locations.add(event.location)
        
        # Use the timestamp of the last pruned event
        last_timestamp = pruned_events[-1].timestamp
        
        self.log_event(
            content=f"SUMMARY OF PAST EVENTS: {summary_content}",
            type=EventType.SUMMARY,
            actors=list(all_actors),
            location="Multiple Locations" if len(all_locations) > 1 else (list(all_locations)[0] if all_locations else None),
            timestamp=last_timestamp,
            tags=["summary", "pruned"]
        )

# --- Bootstrap ---

def bootstrap():
    """Returns a fresh WorldLog instance ready for use."""
    return WorldLog()

