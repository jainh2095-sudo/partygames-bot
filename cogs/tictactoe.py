from __future__ import annotations

import random
import uuid

import discord
from discord import app_commands
from discord.ext import commands

from utils.constants import COIN
from utils.embeds import game_embed, soft_header, success_embed, warning_embed


WIN_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


def winner(board: list[str]) -> str | None:
    for a, b, c in WIN_LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    if " " not in board:
        return "draw"
    return None


def best_move(board: list[str], bot_mark: str, human_mark: str, difficulty: str) -> int:
    empty = [i for i, cell in enumerate(board) if cell == " "]
    if difficulty == "Easy":
        return random.choice(empty)
    for mark in (bot_mark, human_mark):
        for index in empty:
            trial = board.copy()
            trial[index] = mark
            if winner(trial) == mark:
                return index
    if difficulty == "Hard" and 4 in empty:
        return 4
    corners = [i for i in (0, 2, 6, 8) if i in empty]
    return random.choice(corners or empty)


class TicTacToeButton(discord.ui.Button):
    def __init__(self, index: int) -> None:
        super().__init__(label="\u200b", style=discord.ButtonStyle.secondary, row=index // 3, custom_id=f"ttt:{index}")
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, TicTacToeView):
            await view.play(interaction, self.index)


class RematchButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Rematch", emoji="🔁", style=discord.ButtonStyle.success, custom_id="ttt:rematch")

    async def callback(self, interaction: discord.Interaction) -> None:
        old = self.view
        if not isinstance(old, FinishedTTTView):
            return
        view = TicTacToeView(old.bot, old.players, old.best_of, old.difficulty)
        await interaction.response.edit_message(embed=view.embed(interaction.guild), view=view)


class FinishedTTTView(discord.ui.View):
    def __init__(self, bot: commands.Bot, players: list[int], best_of: int, difficulty: str | None) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.players = players
        self.best_of = best_of
        self.difficulty = difficulty
        self.add_item(RematchButton())


class TicTacToeView(discord.ui.View):
    def __init__(self, bot: commands.Bot, players: list[int], best_of: int, difficulty: str | None = None) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.players = players
        self.best_of = best_of
        self.difficulty = difficulty
        self.board = [" "] * 9
        self.turn = 0
        self.scores = {"X": 0, "O": 0}
        self.session_id = str(uuid.uuid4())
        for index in range(9):
            self.add_item(TicTacToeButton(index))
        self.sync_buttons()

    def mark_for(self, user_id: int) -> str:
        return "X" if user_id == self.players[0] else "O"

    def current_user_id(self) -> int:
        return self.players[self.turn % 2]

    def sync_buttons(self, *, disabled: bool = False) -> None:
        for item in self.children:
            if not isinstance(item, TicTacToeButton):
                continue
            mark = self.board[item.index]
            item.label = mark if mark != " " else "\u200b"
            item.disabled = disabled or mark != " "
            if mark == "X":
                item.style = discord.ButtonStyle.danger
            elif mark == "O":
                item.style = discord.ButtonStyle.primary
            else:
                item.style = discord.ButtonStyle.secondary

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.players:
            await interaction.response.send_message("This Tic Tac Toe board belongs to another match.", ephemeral=True)
            return False
        return True

    def render_board(self) -> str:
        symbols = [cell if cell != " " else "⬜" for cell in self.board]
        rows = [" ".join(symbols[i:i + 3]) for i in range(0, 9, 3)]
        return "```\n" + "\n".join(rows) + "\n```"

    def embed(self, guild: discord.Guild, result_text: str | None = None) -> discord.Embed:
        current = guild.get_member(self.current_user_id())
        p1 = guild.get_member(self.players[0])
        p2_name = "PartyGames AI" if self.players[1] == 0 else (guild.get_member(self.players[1]).display_name if guild.get_member(self.players[1]) else "Opponent")
        desc = f"{soft_header('Classic 3x3 showdown')}\n{p1.mention if p1 else 'Player X'} `X` vs **{p2_name}** `O`\n\n{self.render_board()}"
        desc += f"\nScore: `X {self.scores['X']}` • `O {self.scores['O']}` • Best of **{self.best_of}**"
        if result_text:
            desc += f"\n\n{result_text}"
        else:
            desc += f"\n\nTurn: {current.mention if current else 'PartyGames AI'}"
        return game_embed("⭕ Tic Tac Toe ❌", desc, current=current)

    async def save(self, interaction: discord.Interaction) -> None:
        assert interaction.guild and interaction.channel
        await self.bot.db.save_session(
            self.session_id,
            interaction.guild.id,
            interaction.channel.id,
            "tictactoe",
            {"players": self.players, "board": self.board, "turn": self.turn, "scores": self.scores, "best_of": self.best_of},
        )

    async def play(self, interaction: discord.Interaction, index: int) -> None:
        assert interaction.guild
        if interaction.user.id != self.current_user_id():
            await interaction.response.send_message("Wait for your turn.", ephemeral=True)
            return
        if self.board[index] != " ":
            await interaction.response.send_message("That square is already taken.", ephemeral=True)
            return
        self.board[index] = self.mark_for(interaction.user.id)
        await self.after_move(interaction)

    async def after_move(self, interaction: discord.Interaction) -> None:
        assert interaction.guild
        result = winner(self.board)
        if result:
            await self.finish_round(interaction, result)
            return
        self.turn += 1
        if self.players[1] == 0 and self.current_user_id() == 0:
            index = best_move(self.board, "O", "X", self.difficulty or "Medium")
            self.board[index] = "O"
            result = winner(self.board)
            if result:
                await self.finish_round(interaction, result)
                return
            self.turn += 1
        self.sync_buttons()
        await self.save(interaction)
        await interaction.response.edit_message(embed=self.embed(interaction.guild), view=self)

    async def finish_round(self, interaction: discord.Interaction, result: str) -> None:
        assert interaction.guild
        needed = self.best_of // 2 + 1
        result_text = "Round draw."
        if result in ("X", "O"):
            self.scores[result] += 1
            result_text = f"Round winner: **{result}**"
        if self.scores["X"] >= needed or self.scores["O"] >= needed:
            winning_mark = "X" if self.scores["X"] > self.scores["O"] else "O"
            winner_id = self.players[0] if winning_mark == "X" else self.players[1]
            loser_id = self.players[1] if winning_mark == "X" else self.players[0]
            reward_text = "PartyGames AI wins this match."
            if winner_id:
                await self.bot.db.record_game_result(interaction.guild.id, winner_id, "tictactoe", "win")
                await self.bot.db.add_coins(interaction.guild.id, winner_id, 120)
                reward_text = f"<@{winner_id}> earned **120 {COIN}**."
            if loser_id:
                await self.bot.db.record_game_result(interaction.guild.id, loser_id, "tictactoe", "loss")
                await self.bot.db.add_coins(interaction.guild.id, loser_id, 30)
            await self.bot.db.end_session(self.session_id)
            self.stop()
            finished = FinishedTTTView(self.bot, self.players, self.best_of, self.difficulty)
            await interaction.response.edit_message(
                embed=success_embed("Tic Tac Toe complete", f"{result_text}\n{reward_text}"),
                view=finished,
            )
            return
        self.board = [" "] * 9
        self.turn = 0
        self.sync_buttons()
        await self.save(interaction)
        await interaction.response.edit_message(embed=self.embed(interaction.guild, result_text + " Next round!"), view=self)

    async def on_timeout(self) -> None:
        await self.bot.db.end_session(self.session_id)


class TicTacToe(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Play Tic Tac Toe against a player or PartyGames AI.")
    @app_commands.describe(opponent="Leave empty to play the bot", best_of="Match length", difficulty="Bot difficulty")
    @app_commands.choices(
        best_of=[app_commands.Choice(name="Best of 3", value=3), app_commands.Choice(name="Best of 5", value=5)],
        difficulty=[
            app_commands.Choice(name="Easy", value="Easy"),
            app_commands.Choice(name="Medium", value="Medium"),
            app_commands.Choice(name="Hard", value="Hard"),
        ],
    )
    @app_commands.checks.cooldown(1, 10)
    async def tictactoe(
        self,
        interaction: discord.Interaction,
        opponent: discord.Member | None = None,
        best_of: app_commands.Choice[int] | None = None,
        difficulty: app_commands.Choice[str] | None = None,
    ) -> None:
        assert interaction.guild
        if opponent and opponent.bot:
            await interaction.response.send_message(embed=warning_embed("Pick a human opponent", "Use no opponent to play PartyGames AI."), ephemeral=True)
            return
        if opponent and opponent.id == interaction.user.id:
            await interaction.response.send_message("You cannot challenge yourself.", ephemeral=True)
            return
        players = [interaction.user.id, opponent.id if opponent else 0]
        view = TicTacToeView(self.bot, players, best_of.value if best_of else 3, difficulty.value if difficulty else "Medium")
        await view.save(interaction)
        await interaction.response.send_message(embed=view.embed(interaction.guild), view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicTacToe(bot))
