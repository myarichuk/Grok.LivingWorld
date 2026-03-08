import uuid
import json
from datetime import datetime
from typing import List, Dict, Optional, Set, Union
from collections import defaultdict

from .models import Event, Actor, Location, Faction, EventType, AttireItem

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
            # Determine mode based on suffix
            mode = "replace"
            target_key = key
            
            if key.endswith("_add"):
                mode = "add"
                target_key = key[:-4]
            elif key.endswith("_remove"):
                mode = "remove"
                target_key = key[:-7]

            if hasattr(actor.state, target_key):
                old_val = getattr(actor.state, target_key)
                
                # Logic for Replace (Default)
                if mode == "replace":
                    # Ensure list type safety if replacing a list field
                    if isinstance(old_val, list) and not isinstance(value, list):
                        value = [value]
                        
                    if old_val != value:
                        setattr(actor.state, target_key, value)
                        changes.append(f"{target_key}: {old_val} -> {value}")
                
                # Logic for Add (Lists only, with Deduplication)
                elif mode == "add" and isinstance(old_val, list):
                    # Normalize Attire inputs if we are touching the attire list
                    if target_key == "attire":
                        value = [AttireItem.from_mixed(v) for v in (value if isinstance(value, list) else [value])]
                    
                    new_items = value if isinstance(value, list) else [value]
                    added = []
                    for item in new_items:
                        if item not in old_val:
                            old_val.append(item)
                            added.append(item)
                    if added:
                        changes.append(f"Added to {target_key}: {added}")

                # Logic for Remove (Lists only)
                elif mode == "remove" and isinstance(old_val, list):
                    # Normalize Attire inputs for removal matching
                    if target_key == "attire":
                        value = [AttireItem.from_mixed(v) for v in (value if isinstance(value, list) else [value])]
                        
                    items_to_remove = value if isinstance(value, list) else [value]
                    removed = []
                    for item in items_to_remove:
                        if item in old_val:
                            old_val.remove(item)
                            removed.append(item)
                    if removed:
                        changes.append(f"Removed from {target_key}: {removed}")
        
        if changes:
            content = f"State update for {actor_name}: {', '.join(changes)}"
            if reason:
                content += f" ({reason})"
            return self.log_event(content, type=EventType.SYSTEM, actors=[actor_name], tags=["state_change"])
        return None

    # --- Persistence & REPL Ergonomics ---

    def save(self, filepath: str = "campaign.json"):
        with open(filepath, "w") as f:
            f.write(self.to_json())
        print(f"Game saved to {filepath}")

    @classmethod
    def load(cls, filepath: str = "campaign.json") -> 'WorldLog':
        try:
            with open(filepath, "r") as f:
                print(f"Game loaded from {filepath}")
                return cls.from_json(f.read())
        except FileNotFoundError:
            print(f"No save found at {filepath}, starting new world.")
            return cls()

    def log(self, *args, **kwargs): return self.log_event(*args, **kwargs)
    def ctx(self, *args, **kwargs): return self.get_context_summary(*args, **kwargs)
    def roll(self, *args, **kwargs): return self.log_roll(*args, **kwargs)
    def update(self, *args, **kwargs): return self.update_actor_state(*args, **kwargs)

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

        # 3. Recent Events (Fetch first to identify active actors)
        recent_events = self.query_events(limit=event_limit, reverse=True)
        recent_events.reverse()

        # 2.5 Actor Physical State (Context Injection)
        # We only show state for actors mentioned in the recent log to save tokens
        active_actors = set()
        for e in recent_events:
            active_actors.update(e.actors)
            
        if active_actors:
            lines.append("\n=== ACTOR STATE ===")
            for name in sorted(list(active_actors)):
                actor = self.get_actor(name)
                if actor:
                    s = actor.state
                    # Only print if there's something noteworthy (not just standing/unrestricted/healthy)
                    # But we always print attire/pose to ground the scene
                    status_parts = [f"Pose: {s.pose}"]
                    if s.mobility != "unrestricted": status_parts.append(f"Mobility: {s.mobility}")
                    if s.wounds: status_parts.append(f"Wounds: {s.wounds}")
                    if s.restraints: status_parts.append(f"Restraints: {s.restraints}")
                    if s.status_effects: status_parts.append(f"Status: {s.status_effects}")
                    
                    # Attire string
                    attire_str = ", ".join(str(item) for item in s.attire)
                    status_parts.append(f"Wearing: {attire_str}")
                    
                    lines.append(f"{actor.name}: {' | '.join(status_parts)}")

        lines.append("\n=== RECENT LOG ===")
        
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
