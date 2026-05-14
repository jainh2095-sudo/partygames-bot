from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _owner_ids() -> set[int]:
    raw = os.getenv("OWNER_IDS", "")
    return {int(part.strip()) for part in raw.split(",") if part.strip().isdigit()}


@dataclass(frozen=True)
class Settings:
    token: str
    application_id: int | None
    database_path: Path
    owner_ids: set[int]
    log_level: str
    public_invite_url: str
    support_url: str
    bot_name: str = "PartyGames Bot"
    default_prefix: str = "/"


settings = Settings(
    token=os.getenv("DISCORD_TOKEN", ""),
    application_id=int(os.getenv("APPLICATION_ID", "0")) or None,
    database_path=Path(os.getenv("DATABASE_PATH", "data/partygames.sqlite3")),
    owner_ids=_owner_ids(),
    log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    public_invite_url=os.getenv("PUBLIC_INVITE_URL", ""),
    support_url=os.getenv("SUPPORT_URL", ""),
)
