from __future__ import annotations

import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import COGS, PartyGamesBot


async def main() -> None:
    bot = PartyGamesBot()
    await bot.db.connect()
    try:
        for extension in COGS:
            await bot.load_extension(extension)
        command_names = sorted(command.name for command in bot.tree.get_commands())
        print(f"Loaded {len(COGS)} cogs")
        print(f"Registered {len(command_names)} top-level app commands/groups")
        print(", ".join(command_names))
    finally:
        await bot.db.close()
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
