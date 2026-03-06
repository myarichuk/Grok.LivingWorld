import uuid
from datetime import datetime
from typing import List, Dict, Optional, Set
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
