from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


BLOCKED_PATTERNS = [
    r"\b(?:fuck|shit|bitch|cunt|dick|pussy)\b",
    r"\b(?:nigg\w*|fag\w*|retard(?:ed)?)\b",
    r"\b(?:sex|porn|nsfw|nudes?|horny)\b",
    r"\b(?:vodka|beer|wine|whiskey|weed|cocaine|meth)\b",
    r"\b(?:kill yourself|kys)\b",
]

SAFE_REPLACEMENT = "[filtered]"


def sanitize_text(text: str) -> str:
    cleaned = text
    for pattern in BLOCKED_PATTERNS:
        cleaned = re.sub(pattern, SAFE_REPLACEMENT, cleaned, flags=re.IGNORECASE)
    return cleaned


def is_safe_text(text: str) -> bool:
    return sanitize_text(text) == text


@dataclass
class ViolationTracker:
    window: timedelta = timedelta(minutes=20)
    max_warnings: int = 3
    _events: dict[tuple[int, int], list[datetime]] = field(default_factory=lambda: defaultdict(list))

    def add(self, guild_id: int, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        key = (guild_id, user_id)
        self._events[key] = [stamp for stamp in self._events[key] if now - stamp < self.window]
        self._events[key].append(now)
        return len(self._events[key])
