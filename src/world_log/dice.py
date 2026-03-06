import random
import re
from typing import Dict, Any

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
