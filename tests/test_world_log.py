import unittest
import json
from datetime import datetime, timedelta
from src.world_log.models import EventType, Event, Actor, Location
from src.world_log.storage import WorldLog

class TestWorldLog(unittest.TestCase):
    def setUp(self):
        self.log = WorldLog()

    def test_add_actor(self):
        actor = self.log.add_actor("Grok", "A friendly orc", {"strength": 18})
        self.assertEqual(actor.name, "Grok")
        self.assertEqual(actor.description, "A friendly orc")
        self.assertEqual(actor.attributes["strength"], 18)
        
        retrieved = self.log.get_actor("Grok")
        self.assertEqual(retrieved, actor)

    def test_add_location(self):
        loc = self.log.add_location("Tavern", "A bustling place")
        self.assertEqual(loc.name, "Tavern")
        
        retrieved = self.log.get_location("Tavern")
        self.assertEqual(retrieved, loc)

    def test_log_event(self):
        event = self.log.log_event(
            content="Grok enters the tavern.",
            type=EventType.ACTION,
            actors=["Grok"],
            location="Tavern",
            tags=["intro", "peaceful"]
        )
        
        self.assertIsNotNone(event.id)
        self.assertEqual(event.content, "Grok enters the tavern.")
        self.assertEqual(event.actors, ["Grok"])
        self.assertEqual(event.location, "Tavern")
        self.assertEqual(event.tags, ["intro", "peaceful"])
        
        # Check if actor and location were auto-created if they didn't exist
        self.assertIsNotNone(self.log.get_actor("Grok"))
        self.assertIsNotNone(self.log.get_location("Tavern"))

    def test_query_events(self):
        # Setup events
        self.log.log_event("Event 1", actors=["A"], location="L1", type=EventType.ACTION, tags=["t1"])
        self.log.log_event("Event 2", actors=["B"], location="L1", type=EventType.DIALOGUE, tags=["t2"])
        self.log.log_event("Event 3", actors=["A", "B"], location="L2", type=EventType.ACTION, tags=["t1", "t2"])
        
        # Query by actor
        events_a = self.log.query_events(actors="A")
        self.assertEqual(len(events_a), 2)
        self.assertEqual(events_a[0].content, "Event 1")
        self.assertEqual(events_a[1].content, "Event 3")
        
        # Query by multiple actors (AND logic)
        events_ab = self.log.query_events(actors=["A", "B"])
        self.assertEqual(len(events_ab), 1)
        self.assertEqual(events_ab[0].content, "Event 3")
        
        # Query by location
        events_l1 = self.log.query_events(location="L1")
        self.assertEqual(len(events_l1), 2)
        
        # Query by type
        events_dialogue = self.log.query_events(type=EventType.DIALOGUE)
        self.assertEqual(len(events_dialogue), 1)
        self.assertEqual(events_dialogue[0].content, "Event 2")
        
        # Query by tags
        events_t1 = self.log.query_events(tags="t1")
        self.assertEqual(len(events_t1), 2)
        
        events_t1_t2 = self.log.query_events(tags=["t1", "t2"])
        self.assertEqual(len(events_t1_t2), 1)
        self.assertEqual(events_t1_t2[0].content, "Event 3")

    def test_context_string(self):
        self.log.log_event("Hello world", actors=["User"], type=EventType.DIALOGUE)
        self.log.log_event("System initialized", type=EventType.SYSTEM)
        
        context = self.log.get_context_string(limit=5)
        self.assertIn("Hello world", context)
        self.assertIn("System initialized", context)
        self.assertIn("[Actors: User]", context)

    def test_serialization(self):
        # Create a log with some data
        self.log.add_actor("Tester", "A tester")
        self.log.log_event("Test Event", actors=["Tester"], location="Lab")
        
        # Serialize to JSON
        json_str = self.log.to_json()
        
        # Deserialize to a new log
        new_log = WorldLog.from_json(json_str)
        
        # Verify data integrity
        self.assertEqual(len(new_log.events), 1)
        self.assertEqual(len(new_log.actors), 1)
        self.assertEqual(new_log.get_actor("Tester").description, "A tester")
        
        # Verify indexes are rebuilt correctly
        events = new_log.query_events(actors="Tester")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].content, "Test Event")

    def test_pruning_and_summary(self):
        # Add 10 events with increasing timestamps
        base_time = datetime.now()
        for i in range(10):
            self.log.log_event(f"Event {i}", actors=["A"], timestamp=base_time + timedelta(seconds=i))
            
        # Prune to keep last 3
        pruned = self.log.prune_events(keep_last=3)
        
        # Should have pruned 7 events
        self.assertEqual(len(pruned), 7)
        # Should have 3 events remaining
        self.assertEqual(len(self.log.events), 3)
        
        # Verify remaining events are the last ones (7, 8, 9)
        # Note: query_events returns sorted by timestamp, so 0 is oldest remaining
        remaining = self.log.query_events()
        self.assertEqual(remaining[0].content, "Event 7")
        self.assertEqual(remaining[2].content, "Event 9")
        
        # Summarize the pruned events
        self.log.summarize_pruned_events("A lot of stuff happened.", pruned)
        
        # Check summary event was added
        summary_events = self.log.query_events(type=EventType.SUMMARY)
        self.assertEqual(len(summary_events), 1)
        self.assertEqual(summary_events[0].content, "SUMMARY OF PAST EVENTS: A lot of stuff happened.")
        self.assertIn("A", summary_events[0].actors)
        self.assertIn("summary", summary_events[0].tags)

if __name__ == '__main__':
    unittest.main()
