from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands

from config import settings
from utils.constants import COIN, GAME_CHOICES, SHIELD
from utils.embeds import base_embed, section, soft_header, success_embed, warning_embed
from utils.invite import invite_url, permission_summary
from utils.safety import sanitize_text


class RPSView(discord.ui.View):
    def __init__(self, bot: commands.Bot, challenger_id: int, opponent_id: int | None, best_of: int) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.best_of = best_of
        self.choices: dict[int, str] = {}
        self.scores = {challenger_id: 0}
        if opponent_id:
            self.scores[opponent_id] = 0
        else:
            self.scores[0] = 0

    async def choose(self, interaction: discord.Interaction, choice: str) -> None:
        assert interaction.guild
        if self.opponent_id and interaction.user.id not in (self.challenger_id, self.opponent_id):
            await interaction.response.send_message("This RPS match is already full.", ephemeral=True)
            return
        if not self.opponent_id and interaction.user.id != self.challenger_id:
            await interaction.response.send_message("This is a solo bot match.", ephemeral=True)
            return
        self.choices[interaction.user.id] = choice
        if not self.opponent_id:
            await self.resolve(interaction, self.challenger_id, choice, None, random.choice(["Rock", "Paper", "Scissors"]))
            return
        if len(self.choices) < 2:
            await interaction.response.send_message("Choice locked. Waiting for the other player.", ephemeral=True)
            return
        await self.resolve(interaction, self.challenger_id, self.choices[self.challenger_id], self.opponent_id, self.choices[self.opponent_id])

    async def resolve(self, interaction: discord.Interaction, p1: int, c1: str, p2: int | None, c2: str) -> None:
        assert interaction.guild
        beats = {"Rock": "Scissors", "Paper": "Rock", "Scissors": "Paper"}
        note = f"Rock Paper Scissors: **{c1}** vs **{c2}**."
        winner_id = None
        if c1 != c2:
            winner_id = p1 if beats[c1] == c2 else (p2 if p2 is not None else 0)
            self.scores[winner_id] = self.scores.get(winner_id, 0) + 1
            note += f"\nRound winner: {'PartyGames AI' if winner_id == 0 else f'<@{winner_id}>'}"
        else:
            note += "\nRound draw."
        needed = self.best_of // 2 + 1
        if winner_id is not None and self.scores[winner_id] >= needed:
            if winner_id == 0:
                await self.bot.db.record_game_result(interaction.guild.id, self.challenger_id, "rps", "loss")
            else:
                await self.bot.db.record_game_result(interaction.guild.id, winner_id, "rps", "win")
                await self.bot.db.add_coins(interaction.guild.id, winner_id, 90)
                loser_id = self.challenger_id if winner_id != self.challenger_id else self.opponent_id
                if loser_id:
                    await self.bot.db.record_game_result(interaction.guild.id, loser_id, "rps", "loss")
                    await self.bot.db.add_coins(interaction.guild.id, loser_id, 20)
            self.stop()
            reward = "" if winner_id == 0 else f"\nWinner earned **90 {COIN}**."
            await interaction.response.send_message(embed=success_embed("RPS complete", note + reward))
            return
        self.choices.clear()
        score_text = " • ".join(f"{'PartyGames AI' if uid == 0 else f'<@{uid}>'}: {score}" for uid, score in self.scores.items())
        await interaction.response.send_message(embed=base_embed("RPS round", note + f"\nScore: {score_text}"))

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.secondary)
    async def rock(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.choose(interaction, "Rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.secondary)
    async def paper(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.choose(interaction, "Paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.secondary)
    async def scissors(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.choose(interaction, "Scissors")


class Meta(commands.Cog):
    lobby = app_commands.Group(name="lobby", description="Create party game lobbies")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Open the PartyGames command guide.")
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = base_embed("🎉 PartyGames Command Guide", soft_header("Slash-only, button-first, server-safe"))
        embed.add_field(name="Spotlight", value="`/tod start` `/tictactoe` `/connect4` `/battleship`", inline=False)
        embed.add_field(name="Fast Party Prompts", value="`/truth` `/dare` `/wyr` `/nhie` `/randomgame`", inline=True)
        embed.add_field(name="Brain Games", value="`/hangman` `/wordchain` `/questions` `/trivia`", inline=True)
        embed.add_field(name="Progression", value="`/daily` `/profile` `/leaderboard` `/shop` `/buy`", inline=False)
        embed.add_field(name="Server Setup", value="`/invite` `/setup`", inline=True)
        embed.add_field(name="Safety", value=f"{SHIELD} `/report` `/gameban` `/resetcoins`\nCooldowns and content filtering are enabled.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(description="Get the official invite link for adding this bot to a server.")
    async def invite(self, interaction: discord.Interaction) -> None:
        client_id = self.bot.user.id if self.bot.user else settings.application_id
        url = invite_url(client_id)
        if not url:
            await interaction.response.send_message(
                embed=warning_embed(
                    "Invite link unavailable",
                    "Set `APPLICATION_ID` in `.env`, or run this after the bot is logged in.",
                ),
                ephemeral=True,
            )
            return
        embed = base_embed(
            "🔗 Add PartyGames Bot",
            f"{soft_header('Invite this bot to another server')}\n[Open invite link]({url})\n\nRequired permissions:\n{permission_summary()}",
        )
        if settings.support_url:
            embed.add_field(name="Support", value=f"[Support server]({settings.support_url})", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(description="Show the recommended setup checklist for server admins.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction) -> None:
        embed = base_embed("🛠️ PartyGames Setup Checklist", soft_header("Recommended server configuration"))
        embed.add_field(name="1. Permissions", value=permission_summary(), inline=False)
        embed.add_field(name="2. Channels", value="Create a games channel, then use `/lobby create` for private thread lobbies.", inline=False)
        embed.add_field(name="3. Moderation", value="Use `/gameban` for repeated misuse and `/report` for safety issues.", inline=False)
        embed.add_field(name="4. First commands", value="Try `/tod start`, `/tictactoe`, `/connect4`, `/daily`, and `/leaderboard`.", inline=False)
        embed.add_field(name="5. Privacy", value="The bot stores guild/user IDs, coins, game stats, sessions, reports, and purchases in SQLite.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(description="Pick a random game for the server.")
    async def randomgame(self, interaction: discord.Interaction) -> None:
        picked = random.choice(GAME_CHOICES)
        await interaction.response.send_message(embed=base_embed("🎲 Random game picker", section("Tonight's arena pick", f"**{picked}**\nStart a lobby with `/lobby create game:{picked}`.")))

    @lobby.command(name="create", description="Create a private thread lobby for a game.")
    @app_commands.describe(game="Game name for the lobby")
    async def lobby_create(self, interaction: discord.Interaction, game: str) -> None:
        assert interaction.guild and interaction.channel
        clean_game = sanitize_text(game)[:40]
        if hasattr(interaction.channel, "create_thread"):
            try:
                thread = await interaction.channel.create_thread(
                    name=f"party-{clean_game.lower().replace(' ', '-')}",
                    type=discord.ChannelType.private_thread,
                    reason="PartyGames lobby created",
                )
                await thread.add_user(interaction.user)
                await thread.send(embed=base_embed("🎮 Lobby created", f"Game: **{clean_game}**\nInvite players and start when ready."))
                await interaction.response.send_message(embed=success_embed("Lobby ready", thread.mention), ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(embed=warning_embed("Missing thread permissions", "I need permission to create and manage private threads."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=warning_embed("Lobby unavailable", "Create this from a text channel."), ephemeral=True)

    @app_commands.command(description="Report a safety issue to moderators.")
    async def report(self, interaction: discord.Interaction, reason: str, member: discord.Member | None = None) -> None:
        assert interaction.guild
        clean = sanitize_text(reason)
        await self.bot.db.add_report(interaction.guild.id, interaction.user.id, clean, member.id if member else None)
        await interaction.response.send_message(embed=success_embed("Report received", "Thanks for helping keep the server safe."), ephemeral=True)

    @app_commands.command(description="Play Rock Paper Scissors, best of 5 or 10.")
    @app_commands.choices(best_of=[app_commands.Choice(name="Best of 5", value=5), app_commands.Choice(name="Best of 10", value=10)])
    async def rps(self, interaction: discord.Interaction, opponent: discord.Member | None = None, best_of: app_commands.Choice[int] | None = None) -> None:
        if opponent and (opponent.bot or opponent.id == interaction.user.id):
            await interaction.response.send_message("Pick a different human opponent, or leave opponent empty for bot mode.", ephemeral=True)
            return
        view = RPSView(self.bot, interaction.user.id, opponent.id if opponent else None, best_of.value if best_of else 5)
        await interaction.response.send_message(
            content=opponent.mention if opponent else None,
            embed=base_embed("🪨 📄 ✂️ Rock Paper Scissors", "Choose secretly with the buttons. First to majority wins."),
            view=view,
        )

    @app_commands.command(description="Moderator: ban or unban a user from bot games.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def gameban(self, interaction: discord.Interaction, member: discord.Member, banned: bool) -> None:
        assert interaction.guild
        await self.bot.db.set_game_ban(interaction.guild.id, member.id, banned)
        await interaction.response.send_message(embed=success_embed("Game ban updated", f"{member.mention}: `{banned}`"), ephemeral=True)

    @app_commands.command(description="Moderator: reset one member's coins in this server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def resetcoins(self, interaction: discord.Interaction, member: discord.Member) -> None:
        assert interaction.guild
        await self.bot.db.ensure_user(interaction.guild.id, member.id)
        await self.bot.db.db.execute("UPDATE users SET coins = 0 WHERE guild_id = ? AND user_id = ?", (interaction.guild.id, member.id))
        await self.bot.db.db.commit()
        await interaction.response.send_message(embed=success_embed("Coins reset", f"{member.mention}'s Vibe Coins are now 0."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Meta(bot))
