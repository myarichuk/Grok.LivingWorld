import unittest
from datetime import datetime, timedelta
from src.world_log.models import EventType
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
            location="Tavern"
        )
        
        self.assertIsNotNone(event.id)
        self.assertEqual(event.content, "Grok enters the tavern.")
        self.assertEqual(event.actors, ["Grok"])
        self.assertEqual(event.location, "Tavern")
        
        # Check if actor and location were auto-created if they didn't exist
        self.assertIsNotNone(self.log.get_actor("Grok"))
        self.assertIsNotNone(self.log.get_location("Tavern"))

    def test_query_events(self):
        # Setup events
        self.log.log_event("Event 1", actors=["A"], location="L1", type=EventType.ACTION)
        self.log.log_event("Event 2", actors=["B"], location="L1", type=EventType.DIALOGUE)
        self.log.log_event("Event 3", actors=["A", "B"], location="L2", type=EventType.ACTION)
        
        # Query by actor
        events_a = self.log.query_events(actor="A")
        self.assertEqual(len(events_a), 2)
        self.assertEqual(events_a[0].content, "Event 1")
        self.assertEqual(events_a[1].content, "Event 3")
        
        # Query by location
        events_l1 = self.log.query_events(location="L1")
        self.assertEqual(len(events_l1), 2)
        
        # Query by type
        events_dialogue = self.log.query_events(type=EventType.DIALOGUE)
        self.assertEqual(len(events_dialogue), 1)
        self.assertEqual(events_dialogue[0].content, "Event 2")
        
        # Combined query
        events_a_l2 = self.log.query_events(actor="A", location="L2")
        self.assertEqual(len(events_a_l2), 1)
        self.assertEqual(events_a_l2[0].content, "Event 3")

    def test_context_string(self):
        self.log.log_event("Hello world", actors=["User"], type=EventType.DIALOGUE)
        self.log.log_event("System initialized", type=EventType.SYSTEM)
        
        context = self.log.get_context_string(limit=5)
        self.assertIn("Hello world", context)
        self.assertIn("System initialized", context)
        self.assertIn("[Actors: User]", context)

if __name__ == '__main__':
    unittest.main()
