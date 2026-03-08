import random
import re
from typing import Dict, Any, List, Optional

class Dice:
    """
    Utility for rolling dice. Supports standard notation (e.g., "2d6+3"),
    advantage/disadvantage, and raw rolls.
    """
    
    MAX_DICE = 100  # Safety limit to prevent execution hangs
    
    @staticmethod
    def _validate_roll_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lightweight schema validation to ensure the roll result structure is consistent.
        
        Args:
            result (Dict[str, Any]): The dictionary to validate.
            
        Returns:
            Dict[str, Any]: The validated dictionary.
            
        Raises:
            ValueError: If required keys are missing.
            TypeError: If types are incorrect.
        """
        required_keys = {"total", "rolls", "modifier", "die_size", "type", "is_crit", "is_fumble"}
        if not all(key in result for key in required_keys):
            missing = required_keys - result.keys()
            raise ValueError(f"Roll result missing keys: {missing}")
        
        if not isinstance(result["total"], int):
             raise TypeError("Roll total must be an integer")
             
        return result

    @staticmethod
    def roll(notation: str) -> Dict[str, Any]:
        """
        Rolls dice based on standard notation (e.g., '1d20', '2d6+4', '1d8-1').
        Returns a dictionary with details for narrative generation.
        
        Args:
            notation (str): Dice notation string (e.g., "1d20+5").
            
        Returns:
            Dict[str, Any]: A dictionary containing the roll details.
        """
        notation = notation.lower().replace(" ", "")
        # Regex to allow 'd20' (implicit 1) and optional modifiers
        match = re.match(r"^(\d+)?d(\d+)([+-]\d+)?$", notation)
        
        if not match:
            raise ValueError(f"Invalid dice notation: {notation}")
            
        num_dice_str = match.group(1)
        num_dice = int(num_dice_str) if num_dice_str else 1
        
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        
        if num_dice > Dice.MAX_DICE:
            raise ValueError(f"Too many dice: {num_dice}. Max is {Dice.MAX_DICE}.")
            
        if num_dice < 1:
             raise ValueError(f"Number of dice must be at least 1.")

        if die_size < 1:
            raise ValueError(f"Die size must be at least 1.")

        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        total = sum(rolls) + modifier
        
        result = {
            "total": total,
            "rolls": rolls,
            "modifier": modifier,
            "die_size": die_size,
            "type": "normal",
            "is_crit": die_size == 20 and 20 in rolls and num_dice == 1,
            "is_fumble": die_size == 20 and 1 in rolls and num_dice == 1
        }
        return Dice._validate_roll_result(result)

    @staticmethod
    def _roll_multi(die_size: int, modifier: int, mode: str) -> Dict[str, Any]:
        """
        Helper for advantage/disadvantage rolls.
        
        Args:
            die_size (int): Size of the die (default 20).
            modifier (int): Modifier to add to the total.
            mode (str): 'advantage' or 'disadvantage'.
            
        Returns:
            Dict[str, Any]: Roll result.
        """
        if die_size < 1:
            raise ValueError(f"Die size must be at least 1.")
            
        r1 = random.randint(1, die_size)
        r2 = random.randint(1, die_size)
        
        if mode == "advantage":
            kept = max(r1, r2)
        elif mode == "disadvantage":
            kept = min(r1, r2)
        else:
            raise ValueError(f"Invalid mode: {mode}")
            
        result = {
            "total": kept + modifier,
            "rolls": [r1, r2],
            "kept": kept,
            "modifier": modifier,
            "die_size": die_size,
            "type": mode,
            "is_crit": die_size == 20 and kept == 20,
            "is_fumble": die_size == 20 and kept == 1
        }
        return Dice._validate_roll_result(result)

    @staticmethod
    def roll_advantage(die_size: int = 20, modifier: int = 0) -> Dict[str, Any]:
        """
        Rolls 2 dice and takes the higher value.
        Returns a dict with 'total', 'rolls', and 'modifier'.
        """
        return Dice._roll_multi(die_size, modifier, "advantage")

    @staticmethod
    def roll_disadvantage(die_size: int = 20, modifier: int = 0) -> Dict[str, Any]:
        """
        Rolls 2 dice and takes the lower value.
        Returns a dict with 'total', 'rolls', and 'modifier'.
        """
        return Dice._roll_multi(die_size, modifier, "disadvantage")
        
    @staticmethod
    def check(notation: str, dc: int) -> bool:
        """
        Performs a check against a Difficulty Class (DC).
        Returns True if roll >= DC.
        """
        return Dice.roll(notation)["total"] >= dc
