"""Actor memory components for short-term, long-term, and belief tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActorMemory:
    """Narrative memory buckets owned by an actor."""

    short_term: tuple[str, ...] = field(default_factory=tuple)
    long_term: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    beliefs_about: dict[int, str] = field(default_factory=dict)
    known_secrets: tuple[str, ...] = field(default_factory=tuple)
