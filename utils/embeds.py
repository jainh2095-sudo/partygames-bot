from __future__ import annotations

import discord

from datetime import datetime, timezone

from .constants import BRAND_CYAN, BRAND_PINK, BRAND_PURPLE, DIVIDER, ERROR, MEDALS, MINI_DIVIDER, SPARK, SUCCESS, WARNING


def soft_header(text: str) -> str:
    return f"{SPARK} **{text}**\n{DIVIDER}"


def progress_bar(value: int, maximum: int, *, size: int = 10) -> str:
    if maximum <= 0:
        maximum = 1
    filled = max(0, min(size, round(value / maximum * size)))
    return "▰" * filled + "▱" * (size - filled)


def rank_label(index: int) -> str:
    return MEDALS[index - 1] if 1 <= index <= len(MEDALS) else f"`#{index}`"


def base_embed(title: str, description: str = "", *, color: discord.Color = BRAND_PURPLE) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_author(name="PartyGames Bot", icon_url="https://cdn.discordapp.com/embed/avatars/4.png")
    embed.set_footer(text=f"{SPARK} play kind • keep it fun • slash commands only")
    return embed


def success_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, color=SUCCESS)


def warning_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, color=WARNING)


def error_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, color=ERROR)


def game_embed(title: str, description: str = "", *, current: discord.abc.User | None = None) -> discord.Embed:
    embed = base_embed(title, description, color=BRAND_CYAN)
    if current and current.display_avatar:
        embed.set_thumbnail(url=current.display_avatar.url)
    return embed


def party_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, color=BRAND_PINK)


def section(name: str, body: str) -> str:
    return f"**{name}**\n{body}"


def stat_line(label: str, value: str) -> str:
    return f"{MINI_DIVIDER} `{label}` **{value}**"
