from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        self.connection.row_factory = aiosqlite.Row
        await self.connection.execute("PRAGMA journal_mode=WAL")
        await self.connection.execute("PRAGMA foreign_keys=ON")
        await self.connection.execute("PRAGMA busy_timeout=5000")
        await self.migrate()

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()

    @property
    def db(self) -> aiosqlite.Connection:
        if not self.connection:
            raise RuntimeError("Database is not connected.")
        return self.connection

    async def migrate(self) -> None:
        await self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                coins INTEGER NOT NULL DEFAULT 0,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                daily_streak INTEGER NOT NULL DEFAULT 0,
                last_daily TEXT,
                title TEXT DEFAULT 'Rookie Viber',
                favorite_game TEXT DEFAULT 'Truth or Dare',
                game_banned INTEGER NOT NULL DEFAULT 0,
                warnings INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS game_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                draws INTEGER NOT NULL DEFAULT 0,
                played INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, game)
            );

            CREATE TABLE IF NOT EXISTS game_sessions (
                session_id TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                state TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                reporter_id INTEGER NOT NULL,
                target_user_id INTEGER,
                message_id INTEGER,
                reason TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                item_key TEXT NOT NULL,
                item_name TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_users_guild_coins ON users (guild_id, coins DESC);
            CREATE INDEX IF NOT EXISTS idx_users_guild_level ON users (guild_id, level DESC, xp DESC);
            CREATE INDEX IF NOT EXISTS idx_stats_guild_game ON game_stats (guild_id, game, wins DESC);
            CREATE INDEX IF NOT EXISTS idx_sessions_active ON game_sessions (guild_id, active, game);
            CREATE INDEX IF NOT EXISTS idx_reports_guild_created ON reports (guild_id, created_at DESC);
            """
        )
        await self.db.commit()

    async def ensure_guild(self, guild_id: int, name: str) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO guilds (guild_id, name) VALUES (?, ?)",
            (guild_id, name),
        )
        await self.db.commit()

    async def ensure_user(self, guild_id: int, user_id: int) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)",
            (guild_id, user_id),
        )
        await self.db.commit()

    async def is_game_banned(self, guild_id: int, user_id: int) -> bool:
        await self.ensure_user(guild_id, user_id)
        async with self.db.execute(
            "SELECT game_banned FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row["game_banned"]) if row else False

    async def add_coins(self, guild_id: int, user_id: int, amount: int) -> int:
        await self.ensure_user(guild_id, user_id)
        await self.db.execute(
            "UPDATE users SET coins = MAX(0, coins + ?) WHERE guild_id = ? AND user_id = ?",
            (amount, guild_id, user_id),
        )
        await self.db.commit()
        return await self.get_coins(guild_id, user_id)

    async def get_coins(self, guild_id: int, user_id: int) -> int:
        await self.ensure_user(guild_id, user_id)
        async with self.db.execute(
            "SELECT coins FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        return int(row["coins"]) if row else 0

    async def add_xp(self, guild_id: int, user_id: int, amount: int) -> tuple[int, int]:
        await self.ensure_user(guild_id, user_id)
        async with self.db.execute(
            "SELECT xp, level FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        xp = int(row["xp"]) + amount
        level = int(row["level"])
        while xp >= level * 100:
            xp -= level * 100
            level += 1
        await self.db.execute(
            "UPDATE users SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?",
            (xp, level, guild_id, user_id),
        )
        await self.db.commit()
        return xp, level

    async def record_game_result(self, guild_id: int, user_id: int, game: str, result: str) -> None:
        await self.ensure_user(guild_id, user_id)
        await self.db.execute(
            "INSERT OR IGNORE INTO game_stats (guild_id, user_id, game) VALUES (?, ?, ?)",
            (guild_id, user_id, game),
        )
        column = {"win": "wins", "loss": "losses", "draw": "draws"}[result]
        await self.db.execute(
            f"UPDATE game_stats SET {column} = {column} + 1, played = played + 1 WHERE guild_id = ? AND user_id = ? AND game = ?",
            (guild_id, user_id, game),
        )
        await self.add_xp(guild_id, user_id, 20 if result == "win" else 8)
        await self.db.commit()

    async def profile(self, guild_id: int, user_id: int) -> aiosqlite.Row:
        await self.ensure_user(guild_id, user_id)
        async with self.db.execute(
            "SELECT * FROM users WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        return row

    async def totals(self, guild_id: int, user_id: int) -> dict[str, int]:
        async with self.db.execute(
            """
            SELECT COALESCE(SUM(wins), 0) wins, COALESCE(SUM(losses), 0) losses,
                   COALESCE(SUM(draws), 0) draws, COALESCE(SUM(played), 0) played
            FROM game_stats WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row)

    async def leaderboard(self, guild_id: int, board: str, limit: int = 10) -> list[aiosqlite.Row]:
        if board == "coins":
            query = "SELECT user_id, coins score FROM users WHERE guild_id = ? ORDER BY coins DESC LIMIT ?"
        elif board == "level":
            query = "SELECT user_id, level score FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT ?"
        else:
            query = """
            SELECT user_id, SUM(wins) score FROM game_stats
            WHERE guild_id = ? GROUP BY user_id ORDER BY score DESC LIMIT ?
            """
        async with self.db.execute(query, (guild_id, limit)) as cursor:
            return await cursor.fetchall()

    async def save_session(self, session_id: str, guild_id: int, channel_id: int, game: str, state: dict[str, Any]) -> None:
        await self.db.execute(
            """
            INSERT INTO game_sessions (session_id, guild_id, channel_id, game, state, active, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET state = excluded.state, active = 1, updated_at = CURRENT_TIMESTAMP
            """,
            (session_id, guild_id, channel_id, game, json.dumps(state)),
        )
        await self.db.commit()

    async def end_session(self, session_id: str) -> None:
        await self.db.execute(
            "UPDATE game_sessions SET active = 0, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,),
        )
        await self.db.commit()

    async def add_report(self, guild_id: int, reporter_id: int, reason: str, target_user_id: int | None = None, message_id: int | None = None) -> None:
        await self.db.execute(
            "INSERT INTO reports (guild_id, reporter_id, target_user_id, message_id, reason) VALUES (?, ?, ?, ?, ?)",
            (guild_id, reporter_id, target_user_id, message_id, reason[:500]),
        )
        await self.db.commit()

    async def set_game_ban(self, guild_id: int, user_id: int, banned: bool) -> None:
        await self.ensure_user(guild_id, user_id)
        await self.db.execute(
            "UPDATE users SET game_banned = ? WHERE guild_id = ? AND user_id = ?",
            (1 if banned else 0, guild_id, user_id),
        )
        await self.db.commit()

    async def add_purchase(self, guild_id: int, user_id: int, item_key: str, item_name: str) -> None:
        await self.db.execute(
            "INSERT INTO purchases (guild_id, user_id, item_key, item_name) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, item_key, item_name),
        )
        await self.db.commit()
