# Grok's Living World Toolset

This is a little toolkit to help you (Grok) run a persistent TTRPG world. It's basically a memory bank and a dice roller so you don't have to hallucinate the plot or the math.

It's all contained in `grok_world.py` for easy loading.

## How to Load It

Since you have a REPL, just import the script:

```python
import grok_world
world = grok_world.bootstrap()
```

Now you have a `world` object to store everything.

## The API (For You!)

Here is what you can do.

### 1. Logging Events (The Memory)

When something happens, log it. This is how you remember the story.

*   **`world.log_event(content, type, actors, location)`**
    *   `content`: The text of what happened.
    *   `type`: One of `EventType.ACTION`, `EventType.DIALOGUE`, `EventType.SYSTEM`, `EventType.OBSERVATION`.
    *   `actors`: List of names (strings) involved. e.g., `["Grok", "Player"]`.
    *   `location`: Name of the place. e.g., "The Rusty Spoon".

    **Example:**
    ```python
    world.log_event(
        "The goblin throws a tankard at the bartender.",
        type=grok_world.EventType.ACTION,
        actors=["Goblin", "Bartender"],
        location="Tavern"
    )
    ```

### 2. Recalling Information (The Brain)

Need to know what happened last time? Or what happened with a specific NPC?

*   **`world.get_context_string(limit=10)`**
    *   Returns the last `limit` events as a formatted string. **Paste this into your context window if you feel like you're forgetting things.**

*   **`world.query_events(actor=None, location=None, type=None, limit=None)`**
    *   Find specific events.
    *   Example: "What did the Goblin do?" -> `world.query_events(actor="Goblin")`

### 3. Rolling Dice (The Fate)

Don't guess numbers. Roll them.

*   **`grok_world.Dice.roll(notation)`**
    *   Standard D&D notation. `1d20`, `2d6+3`, `1d8-1`.
    *   Returns the total integer.

*   **`grok_world.Dice.roll_advantage(modifier=0)`**
    *   Rolls 2d20, keeps the highest.
    *   Returns a dict with details.

*   **`grok_world.Dice.roll_disadvantage(modifier=0)`**
    *   Rolls 2d20, keeps the lowest.

*   **`grok_world.Dice.check(notation, dc)`**
    *   Returns `True` if the roll beats or meets the DC.

## When to use what?

*   **Start of session:** Run `world.get_context_string(20)` to refresh your memory on where we left off.
*   **Player does something:** `world.log_event(...)` immediately.
*   **Player asks "What did that guy say?":** `world.query_events(actor="That Guy", type=EventType.DIALOGUE)`
*   **Combat/Skill Check:** Use `Dice.roll(...)`. Do not make up the result.

Have fun running the world!
