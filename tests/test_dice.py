import unittest
from unittest.mock import patch
from src.world_log.dice import Dice

class TestDice(unittest.TestCase):
    
    @patch('random.randint')
    def test_roll_basic(self, mock_randint):
        # Mock random.randint to always return 3
        mock_randint.return_value = 3
        
        # 1d6 -> 3
        self.assertEqual(Dice.roll("1d6"), 3)
        
        # 2d6 -> 3 + 3 = 6
        self.assertEqual(Dice.roll("2d6"), 6)
        
    @patch('random.randint')
    def test_roll_with_modifier(self, mock_randint):
        mock_randint.return_value = 4
        
        # 1d20+5 -> 4 + 5 = 9
        self.assertEqual(Dice.roll("1d20+5"), 9)
        
        # 1d8-1 -> 4 - 1 = 3
        self.assertEqual(Dice.roll("1d8-1"), 3)

    def test_invalid_notation(self):
        with self.assertRaises(ValueError):
            Dice.roll("invalid")
        with self.assertRaises(ValueError):
            Dice.roll("d20") # Missing number of dice

    @patch('random.randint')
    def test_roll_advantage(self, mock_randint):
        # Mock side_effect to return different values for consecutive calls
        mock_randint.side_effect = [5, 15]
        
        result = Dice.roll_advantage()
        self.assertEqual(result['kept'], 15)
        self.assertEqual(result['total'], 15)
        self.assertEqual(result['type'], 'advantage')
        self.assertEqual(result['rolls'], [5, 15])

    @patch('random.randint')
    def test_roll_disadvantage(self, mock_randint):
        mock_randint.side_effect = [5, 15]
        
        result = Dice.roll_disadvantage()
        self.assertEqual(result['kept'], 5)
        self.assertEqual(result['total'], 5)
        self.assertEqual(result['type'], 'disadvantage')
        self.assertEqual(result['rolls'], [5, 15])

    @patch('random.randint')
    def test_check(self, mock_randint):
        mock_randint.return_value = 10
        
        # 1d20 (10) >= 10 -> True
        self.assertTrue(Dice.check("1d20", 10))
        
        # 1d20 (10) >= 11 -> False
        self.assertFalse(Dice.check("1d20", 11))

if __name__ == '__main__':
    unittest.main()
