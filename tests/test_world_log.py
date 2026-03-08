import unittest
from unittest.mock import patch
import sys
import os

# Add src to path to allow imports if running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from world_log.dice import Dice
from world_log.storage import WorldLog

class TestDice(unittest.TestCase):
    
    def test_roll_parsing_standard(self):
        """Test standard dice notation parsing."""
        result = Dice.roll("1d20+5")
        self.assertEqual(result["die_size"], 20)
        self.assertEqual(result["modifier"], 5)
        self.assertEqual(len(result["rolls"]), 1)
        self.assertEqual(result["type"], "normal")

    def test_roll_parsing_implicit_count(self):
        """Test notation without leading number (e.g., 'd8')."""
        result = Dice.roll("d8")
        self.assertEqual(result["die_size"], 8)
        self.assertEqual(len(result["rolls"]), 1)
        self.assertEqual(result["modifier"], 0)

    def test_roll_parsing_multiple_dice(self):
        """Test rolling multiple dice with negative modifier."""
        result = Dice.roll("2d6-1")
        self.assertEqual(len(result["rolls"]), 2)
        self.assertEqual(result["modifier"], -1)
        self.assertEqual(result["die_size"], 6)

    def test_roll_limits(self):
        """Test that exceeding MAX_DICE raises ValueError."""
        with self.assertRaises(ValueError):
            Dice.roll("101d6")

    def test_roll_invalid_notation(self):
        """Test that invalid notation raises ValueError."""
        with self.assertRaises(ValueError):
            Dice.roll("invalid")
        with self.assertRaises(ValueError):
            Dice.roll("1d20+a")

    @patch('world_log.dice.random.randint')
    def test_crit_and_fumble_normal(self, mock_rand):
        """Test critical hit and fumble detection on normal rolls."""
        # Test Crit (20 on d20)
        mock_rand.return_value = 20
        result = Dice.roll("1d20")
        self.assertTrue(result["is_crit"])
        self.assertFalse(result["is_fumble"])

        # Test Fumble (1 on d20)
        mock_rand.return_value = 1
        result = Dice.roll("1d20")
        self.assertFalse(result["is_crit"])
        self.assertTrue(result["is_fumble"])
        
        # Test non-d20 (20 on d100 is not a crit)
        mock_rand.return_value = 20
        result = Dice.roll("1d100")
        self.assertFalse(result["is_crit"])

    @patch('world_log.dice.random.randint')
    def test_advantage(self, mock_rand):
        """Test advantage mechanics (take higher)."""
        mock_rand.side_effect = [5, 15] # Rolls 5 and 15
        result = Dice.roll_advantage(die_size=20, modifier=2)
        
        self.assertEqual(result["kept"], 15)
        self.assertEqual(result["total"], 17) # 15 + 2
        self.assertEqual(result["type"], "advantage")
        self.assertEqual(result["rolls"], [5, 15])

    @patch('world_log.dice.random.randint')
    def test_disadvantage(self, mock_rand):
        """Test disadvantage mechanics (take lower)."""
        mock_rand.side_effect = [5, 15] # Rolls 5 and 15
        result = Dice.roll_disadvantage(die_size=20, modifier=2)
        
        self.assertEqual(result["kept"], 5)
        self.assertEqual(result["total"], 7) # 5 + 2
        self.assertEqual(result["type"], "disadvantage")

    def test_check_method(self):
        """Test the simple check method."""
        with patch('world_log.dice.Dice.roll') as mock_roll:
            mock_roll.return_value = {"total": 15}
            self.assertTrue(Dice.check("1d20", 10))
            self.assertFalse(Dice.check("1d20", 20))


class TestWorldState(unittest.TestCase):
    def setUp(self):
        self.world = WorldLog()

    def test_faction_standing_mechanics(self):
        """Test faction reputation clamping and relationship strings."""
        f = self.world.get_or_create_faction("Thieves Guild", "Sneaky")
        self.assertEqual(f.standing, 0)
        self.assertEqual(f.get_relationship(), "Neutral")
        
        # Test adjustment
        self.world.adjust_faction_standing("Thieves Guild", -50)
        self.assertEqual(f.get_relationship(), "Hostile")
        
        # Test clamping
        self.world.adjust_faction_standing("Thieves Guild", -60) # Should go to -110, clamped to -100
        self.assertEqual(f.standing, -100)
        self.assertEqual(f.get_relationship(), "Nemesis")

    def test_location_flow_and_logging(self):
        """Test entering locations and logging events."""
        loc = self.world.enter_location("Tavern", "A smoky room.")
        self.assertEqual(self.world.current_location_name, "Tavern")
        self.assertTrue(loc.visited)
        
        # Check global log for discovery event
        # Note: WorldLog events are objects, not strings
        events = self.world.query_events()
        self.assertIn("Party discovered Tavern.", events[0].content)
        
        # Log specific event
        self.world.log_event("Brawl started.")
        
        # Check location history (formatted string)
        self.assertIn("Brawl started", loc.local_history[0])
        self.assertIn("Brawl started", self.world.query_events()[-1].content)

    def test_context_summary_generation(self):
        """Test that the context summary includes key information."""
        self.world.enter_location("Dungeon", "Dark and damp.")
        
        # Add an actor and event so they appear in summary
        self.world.add_actor("Alice")
        self.world.update_actor_state("Alice", {"pose": "kneeling", "wounds": ["cut"]})
        self.world.log_event("Alice found a key.", actors=["Alice"])
        
        summary = self.world.get_context_summary(event_limit=5)
        
        self.assertIn("Current Location: Dungeon", summary)
        self.assertIn("Alice found a key", summary)
        # Check for physical state injection
        self.assertIn("Pose: kneeling", summary)
        self.assertIn("Wounds: ['cut']", summary)

    def test_actor_physical_state(self):
        """Test tracking of physical state (pose, wounds, etc)."""
        actor = self.world.add_actor("Bob", "A fighter")
        
        # Default state
        self.assertEqual(actor.state.pose, "standing")
        self.assertEqual(actor.state.restraints, [])
        
        # Update state via helper
        self.world.update_actor_state("Bob", {
            "pose": "prone",
            "restraints_add": "rope",
            "wounds_add": ["scratch"],
            "mobility": "crawling"
        }, reason="Tripped")
        
        self.assertEqual(actor.state.pose, "prone")
        self.assertEqual(actor.state.restraints, ["rope"])
        self.assertEqual(actor.state.mobility, "crawling")
        
        # Test Deduplication
        self.world.update_actor_state("Bob", {"wounds_add": ["scratch"]})
        self.assertEqual(len(actor.state.wounds), 1) # Should still be 1
        
        # Test Removal
        self.world.update_actor_state("Bob", {"wounds_remove": ["scratch"]})
        self.assertEqual(len(actor.state.wounds), 0)
        
        # Test Rich Attire (Layers)
        pauldron = {"item": "Pauldron", "layer": "outer", "condition": "fine"}
        # Note: The system now converts this dict to an AttireItem
        self.world.update_actor_state("Bob", {"attire_add": [pauldron]})
        self.assertTrue(any(a.name == "Pauldron" for a in actor.state.attire))
        
        # Test Replacement (Attire)
        new_outfit = ["Rags"]
        self.world.update_actor_state("Bob", {"attire": new_outfit})
        self.assertEqual(actor.state.attire[0].name, "Rags")
        
        # Verify log
        last_event = self.world.query_events()[-1]
        self.assertIn("attire: ", last_event.content)

if __name__ == '__main__':
    unittest.main()