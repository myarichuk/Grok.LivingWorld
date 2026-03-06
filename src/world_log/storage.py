import uuid
import json
from datetime import datetime
from typing import List, Dict, Optional, Set, Union
from collections import defaultdict

from .models import Event, Actor, Location, EventType

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
                  tags: List[str] = None,
                  timestamp: datetime = None) -> Event:
        
        if actors is None:
            actors = []
        if metadata is None:
            metadata = {}
        if tags is None:
            tags = []
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
            metadata=metadata,
            tags=tags
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

    def get_context_string(self, limit: int = 10) -> str:
        """Returns a formatted string of recent events suitable for LLM context."""
        recent_events = self.query_events(limit=limit, reverse=True)
        recent_events.reverse()
        
        lines = []
        for event in recent_events:
            timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            actors_str = f" [Actors: {', '.join(event.actors)}]" if event.actors else ""
            loc_str = f" [Loc: {event.location}]" if event.location else ""
            tags_str = f" [Tags: {', '.join(event.tags)}]" if event.tags else ""
            lines.append(f"[{timestamp_str}] ({event.type.value}){actors_str}{loc_str}{tags_str}: {event.content}")
            
        return "\n".join(lines)

    def to_json(self) -> str:
        """Serializes the entire world state to a JSON string."""
        data = {
            "events": [event.to_dict() for event in self.events.values()],
            "actors": [actor.to_dict() for actor in self.actors.values()],
            "locations": [location.to_dict() for location in self.locations.values()]
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'WorldLog':
        """Deserializes a WorldLog from a JSON string."""
        data = json.loads(json_str)
        world = cls()
        
        for actor_data in data.get("actors", []):
            actor = Actor.from_dict(actor_data)
            world.actors[actor.name] = actor
            
        for loc_data in data.get("locations", []):
            loc = Location.from_dict(loc_data)
            world.locations[loc.name] = loc
            
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
