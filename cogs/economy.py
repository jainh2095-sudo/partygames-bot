from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.constants import COIN, TROPHY
from utils.embeds import base_embed, progress_bar, rank_label, soft_header, stat_line, success_embed


SHOP_ITEMS = {
    "title": ("Funny title", 1200, "Sets your profile title to Certified Vibe Strategist."),
    "badge": ("Profile badge", 5000, "Adds a collectible purchase record for future profile badges."),
    "dare_booster": ("Dare booster", 750, "Adds a booster purchase record moderators can honor in events."),
    "sound": ("Sound effect token", 900, "Adds a redeemable sound effect token record."),
    "color": ("Color role voucher", 2500, "Adds a role color voucher record for server staff."),
}


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Claim your daily Vibe Coins and streak bonus.")
    @app_commands.checks.cooldown(1, 10)
    async def daily(self, interaction: discord.Interaction) -> None:
        assert interaction.guild
        db = self.bot.db
        user = await db.profile(interaction.guild.id, interaction.user.id)
        now = datetime.now(timezone.utc)
        last_daily = datetime.fromisoformat(user["last_daily"]) if user["last_daily"] else None
        if last_daily and now - last_daily < timedelta(hours=20):
            remaining = timedelta(hours=20) - (now - last_daily)
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            await interaction.response.send_message(
                embed=base_embed("Daily already claimed", f"Come back in `{hours}h {minutes}m` for more {COIN}."),
                ephemeral=True,
            )
            return
        streak = user["daily_streak"] + 1 if last_daily and now - last_daily < timedelta(hours=48) else 1
        reward = 100 + min(streak, 14) * 10
        await db.add_coins(interaction.guild.id, interaction.user.id, reward)
        await db.db.execute(
            "UPDATE users SET daily_streak = ?, last_daily = ? WHERE guild_id = ? AND user_id = ?",
            (streak, now.isoformat(), interaction.guild.id, interaction.user.id),
        )
        await db.db.commit()
        bar = progress_bar(min(streak, 14), 14)
        embed = success_embed(
            "Daily reward claimed",
            f"{soft_header('Daily streak')}\n{bar} **{streak} days**\n\nYou earned **{reward} {COIN}**.",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="View your PartyGames profile, stats, level, and coins.")
    async def profile(self, interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        assert interaction.guild
        target = member or interaction.user
        user = await self.bot.db.profile(interaction.guild.id, target.id)
        totals = await self.bot.db.totals(interaction.guild.id, target.id)
        win_rate = 0 if totals["played"] == 0 else round(totals["wins"] / totals["played"] * 100)
        next_level = max(user["level"] * 100, 1)
        xp_bar = progress_bar(user["xp"], next_level)
        embed = base_embed(
            f"🌈 {target.display_name}'s profile",
            f"{soft_header(user['title'])}\n{xp_bar} `{user['xp']}/{next_level} XP`\n",
            color=discord.Color.from_rgb(255, 76, 180),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Wallet", value=f"{stat_line('coins', f'{user['coins']:,} {COIN}')}\n{stat_line('level', str(user['level']))}", inline=True)
        embed.add_field(name="Arena Stats", value=f"{stat_line('wins', str(totals['wins']))}\n{stat_line('played', str(totals['played']))}", inline=True)
        embed.add_field(name="Style", value=f"{stat_line('win rate', f'{win_rate}%')}\n{stat_line('favorite', user['favorite_game'])}", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Show server leaderboards for wins, coins, or level.")
    @app_commands.describe(board="Leaderboard type")
    @app_commands.choices(board=[
        app_commands.Choice(name="Most wins", value="wins"),
        app_commands.Choice(name="Most coins", value="coins"),
        app_commands.Choice(name="Highest level", value="level"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, board: app_commands.Choice[str]) -> None:
        assert interaction.guild
        rows = await self.bot.db.leaderboard(interaction.guild.id, board.value)
        lines = []
        for index, row in enumerate(rows, start=1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"User {row['user_id']}"
            lines.append(f"{rank_label(index)} **{name}**\n`{row['score']}` points")
        embed = base_embed(f"{TROPHY} {board.name}", f"{soft_header(interaction.guild.name)}\n" + ("\n\n".join(lines) or "No leaderboard data yet."))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(description="Browse the Vibe Coin shop.")
    async def shop(self, interaction: discord.Interaction) -> None:
        embed = base_embed("🛍️ Vibe Shop", f"{soft_header('Cosmetics, boosts, and server-safe flexes')}\nUse `/buy item:<key>` when something catches your eye.")
        for key, (name, price, description) in SHOP_ITEMS.items():
            embed.add_field(name=f"{name}", value=f"`{key}` • **{price:,} {COIN}**\n{description}", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(description="Buy a cosmetic or event item with Vibe Coins.")
    @app_commands.describe(item="Shop item key")
    @app_commands.choices(item=[
        app_commands.Choice(name="Funny title", value="title"),
        app_commands.Choice(name="Profile badge", value="badge"),
        app_commands.Choice(name="Dare booster", value="dare_booster"),
        app_commands.Choice(name="Sound effect token", value="sound"),
        app_commands.Choice(name="Color role voucher", value="color"),
    ])
    async def buy(self, interaction: discord.Interaction, item: app_commands.Choice[str]) -> None:
        assert interaction.guild
        key = item.value
        name, price, _ = SHOP_ITEMS[key]
        balance = await self.bot.db.get_coins(interaction.guild.id, interaction.user.id)
        if balance < price:
            await interaction.response.send_message(
                embed=base_embed("Not enough Vibe Coins", f"You need **{price - balance:,}** more {COIN} for **{name}**."),
                ephemeral=True,
            )
            return
        await self.bot.db.add_coins(interaction.guild.id, interaction.user.id, -price)
        await self.bot.db.add_purchase(interaction.guild.id, interaction.user.id, key, name)
        if key == "title":
            await self.bot.db.db.execute(
                "UPDATE users SET title = ? WHERE guild_id = ? AND user_id = ?",
                ("Certified Vibe Strategist", interaction.guild.id, interaction.user.id),
            )
            await self.bot.db.db.commit()
        await interaction.response.send_message(embed=success_embed("Purchase complete", f"You bought **{name}** for **{price:,} {COIN}**."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
