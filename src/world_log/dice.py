import random
import re
from typing import Dict, Any

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
