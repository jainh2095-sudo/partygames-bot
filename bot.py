from __future__ import annotations

import asyncio
import logging
from itertools import cycle

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import settings
from database import Database
from utils.embeds import error_embed, soft_header


COGS = [
    "cogs.economy",
    "cogs.truth_or_dare",
    "cogs.tictactoe",
    "cogs.connect4",
    "cogs.additional_games",
    "cogs.meta",
]


class PartyGamesTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        client = self.client
        if not isinstance(client, PartyGamesBot) or not interaction.guild:
            return True
        await client.db.ensure_guild(interaction.guild.id, interaction.guild.name)
        if interaction.user and await client.db.is_game_banned(interaction.guild.id, interaction.user.id):
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=error_embed("Game access paused", "A moderator has temporarily blocked you from PartyGames."),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    embed=error_embed("Game access paused", "A moderator has temporarily blocked you from PartyGames."),
                    ephemeral=True,
                )
            return False
        return True


class PartyGamesBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            tree_cls=PartyGamesTree,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )
        self.db = Database(settings.database_path)
        self._synced_commands = False
        self.status_messages = cycle([
            "Truth or Dare sparks flying",
            "Connect 4 showdowns",
            "Tic Tac Toe mind games",
            "/help for party mode",
        ])

    async def setup_hook(self) -> None:
        await self.db.connect()
        from cogs.truth_or_dare import PromptView

        self.add_view(PromptView())
        for extension in COGS:
            await self.load_extension(extension)
        self.tree.on_error = self.on_app_command_error
        self.rotate_status.start()
        logging.info("Loaded %s cogs", len(COGS))

    async def close(self) -> None:
        self.rotate_status.cancel()
        await self.db.close()
        await super().close()

    async def on_ready(self) -> None:
        if self.user:
            logging.info("Logged in as %s (%s)", self.user, self.user.id)
        if not self._synced_commands:
            try:
                synced = await self.tree.sync()
                self._synced_commands = True
                logging.info("Synced %s global app commands", len(synced))
            except discord.HTTPException:
                logging.exception("Failed to sync app commands")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.db.ensure_guild(guild.id, guild.name)
        me = guild.me or (guild.get_member(self.user.id) if self.user else None)
        channel = None
        if me:
            channel = guild.system_channel if guild.system_channel and guild.system_channel.permissions_for(me).send_messages else None
            channel = channel or next((c for c in guild.text_channels if c.permissions_for(me).send_messages), None)
        if channel:
            await channel.send(
                embed=discord.Embed(
                    title="🎉 PartyGames Bot joined the arena",
                    description=f"{soft_header('Safe party games for busy Discord servers')}\nUse `/help` to open the command guide.\n\nButtons, rich embeds, Vibe Coins, leaderboards, and multiplayer lobbies are ready.",
                    color=discord.Color.from_rgb(145, 70, 255),
                )
            )

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        if not isinstance(error, discord.app_commands.CommandOnCooldown):
            logging.exception("App command failed: %s", error)
        description = "Something went sideways while handling that command."
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            description = f"Slow down a little. Try again in `{error.retry_after:.1f}s`."
        elif isinstance(error, discord.app_commands.MissingPermissions):
            description = "You need extra server permissions for that command."
        embed = error_embed("Command failed", description)
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tasks.loop(seconds=45)
    async def rotate_status(self) -> None:
        await self.change_presence(activity=discord.Game(next(self.status_messages)))


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    if not settings.token:
        raise RuntimeError("DISCORD_TOKEN is missing. Copy .env.example to .env and add your bot token.")
    async with PartyGamesBot() as bot:
        await bot.start(settings.token)


if __name__ == "__main__":
    asyncio.run(main())
