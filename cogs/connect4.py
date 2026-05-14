from __future__ import annotations

import uuid

import discord
from discord import app_commands
from discord.ext import commands

from utils.constants import COIN
from utils.embeds import game_embed, soft_header, success_embed, warning_embed


ROWS = 6
COLS = 7
EMPTY = "⚫"
RED = "🔴"
YELLOW = "🟡"


def check_connect4(board: list[list[str]]) -> str | None:
    directions = ((1, 0), (0, 1), (1, 1), (1, -1))
    for row in range(ROWS):
        for col in range(COLS):
            piece = board[row][col]
            if piece == EMPTY:
                continue
            for dr, dc in directions:
                if all(
                    0 <= row + dr * step < ROWS
                    and 0 <= col + dc * step < COLS
                    and board[row + dr * step][col + dc * step] == piece
                    for step in range(4)
                ):
                    return piece
    if all(board[0][col] != EMPTY for col in range(COLS)):
        return "draw"
    return None


class ColumnButton(discord.ui.Button):
    def __init__(self, col: int) -> None:
        super().__init__(label=str(col + 1), style=discord.ButtonStyle.primary, row=0, custom_id=f"c4:{col}")
        self.col = col

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, Connect4View):
            await view.drop(interaction, self.col)


class Connect4View(discord.ui.View):
    def __init__(self, bot: commands.Bot, players: list[int]) -> None:
        super().__init__(timeout=1200)
        self.bot = bot
        self.players = players
        self.turn = 0
        self.board = [[EMPTY for _ in range(COLS)] for _ in range(ROWS)]
        self.session_id = str(uuid.uuid4())
        for col in range(COLS):
            self.add_item(ColumnButton(col))

    def current_user_id(self) -> int:
        return self.players[self.turn % 2]

    def piece_for_turn(self) -> str:
        return RED if self.turn % 2 == 0 else YELLOW

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.players:
            await interaction.response.send_message("This Connect 4 board belongs to another match.", ephemeral=True)
            return False
        return True

    def board_text(self) -> str:
        board = "\n".join("".join(row) for row in self.board) + "\n1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"
        return "```\n" + board + "\n```"

    def embed(self, guild: discord.Guild, note: str | None = None) -> discord.Embed:
        current = guild.get_member(self.current_user_id())
        p1 = guild.get_member(self.players[0])
        p2 = guild.get_member(self.players[1])
        desc = f"{soft_header('Drop pieces, connect four')}\n{p1.mention if p1 else 'Player 1'} {RED} vs {p2.mention if p2 else 'Player 2'} {YELLOW}\n\n{self.board_text()}"
        desc += f"\nTurn: {current.mention if current else 'Player'} {self.piece_for_turn()}"
        if note:
            desc += f"\n{note}"
        return game_embed("🔴 Connect 4 🟡", desc, current=current)

    async def save(self, interaction: discord.Interaction) -> None:
        assert interaction.guild and interaction.channel
        await self.bot.db.save_session(
            self.session_id,
            interaction.guild.id,
            interaction.channel.id,
            "connect4",
            {"players": self.players, "turn": self.turn, "board": self.board},
        )

    async def drop(self, interaction: discord.Interaction, col: int) -> None:
        assert interaction.guild
        if interaction.user.id != self.current_user_id():
            await interaction.response.send_message("Wait for your turn.", ephemeral=True)
            return
        placed = False
        for row in range(ROWS - 1, -1, -1):
            if self.board[row][col] == EMPTY:
                self.board[row][col] = self.piece_for_turn()
                placed = True
                break
        if not placed:
            await interaction.response.send_message("That column is full.", ephemeral=True)
            return
        result = check_connect4(self.board)
        if result:
            await self.finish(interaction, result)
            return
        self.turn += 1
        await self.save(interaction)
        await interaction.response.edit_message(embed=self.embed(interaction.guild), view=self)

    async def finish(self, interaction: discord.Interaction, result: str) -> None:
        assert interaction.guild
        await self.bot.db.end_session(self.session_id)
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if result == "draw":
            for user_id in self.players:
                await self.bot.db.record_game_result(interaction.guild.id, user_id, "connect4", "draw")
                await self.bot.db.add_coins(interaction.guild.id, user_id, 45)
            await interaction.response.edit_message(
                embed=warning_embed("Connect 4 draw", f"Both players earned **45 {COIN}**."),
                view=self,
            )
            return
        winner_index = 0 if result == RED else 1
        winner_id = self.players[winner_index]
        loser_id = self.players[1 - winner_index]
        await self.bot.db.record_game_result(interaction.guild.id, winner_id, "connect4", "win")
        await self.bot.db.record_game_result(interaction.guild.id, loser_id, "connect4", "loss")
        await self.bot.db.add_coins(interaction.guild.id, winner_id, 160)
        await self.bot.db.add_coins(interaction.guild.id, loser_id, 35)
        member = interaction.guild.get_member(winner_id)
        await interaction.response.edit_message(
            embed=success_embed("Connect 4 victory", f"{member.mention if member else 'Winner'} wins and earns **160 {COIN}**!\n\n{self.board_text()}"),
            view=self,
        )

    async def on_timeout(self) -> None:
        await self.bot.db.end_session(self.session_id)


class Connect4(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Challenge another player to Connect 4.")
    @app_commands.checks.cooldown(1, 10)
    async def connect4(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        assert interaction.guild
        if opponent.bot or opponent.id == interaction.user.id:
            await interaction.response.send_message(embed=warning_embed("Choose another human player", "Connect 4 is a 1v1 multiplayer game."), ephemeral=True)
            return
        view = Connect4View(self.bot, [interaction.user.id, opponent.id])
        await interaction.response.send_message(content=opponent.mention, embed=view.embed(interaction.guild), view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Connect4(bot))
