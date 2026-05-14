from __future__ import annotations

import random
import uuid

import discord
from discord import app_commands
from discord.ext import commands

from utils.constants import COIN
from utils.embeds import base_embed, game_embed, progress_bar, section, soft_header, success_embed, warning_embed
from utils.safety import is_safe_text, sanitize_text


WYR_PROMPTS = [
    ("Speak every language", "Play every instrument"),
    ("Teleport once a day", "Pause time for five minutes"),
    ("Have perfect memory", "Have perfect focus"),
    ("Explore the ocean", "Explore space"),
]

NHIE_PROMPTS = [
    "Never have I ever laughed so hard I could not finish a sentence.",
    "Never have I ever sent a message to the wrong chat.",
    "Never have I ever stayed up too late finishing a game or show.",
    "Never have I ever won a game by pure luck.",
]

HANGMAN_WORDS = ["friendship", "galaxy", "festival", "puzzle", "rainbow", "culture", "playlist", "language"]

QUESTION_TARGETS = {
    "piano": {"music", "instrument", "keys", "sound", "practice"},
    "passport": {"travel", "country", "airport", "document", "identity"},
    "moon": {"space", "night", "sky", "orbit", "bright"},
    "camera": {"photo", "picture", "lens", "memory", "video"},
}

TRIVIA = [
    ("Which planet is known as the Red Planet?", ["Mars", "Venus", "Jupiter", "Mercury"], 0),
    ("What is the largest ocean on Earth?", ["Atlantic", "Indian", "Pacific", "Arctic"], 2),
    ("Which language has the most native speakers?", ["English", "Mandarin Chinese", "Spanish", "Hindi"], 1),
    ("What does HTML stand for?", ["HyperText Markup Language", "High Tech Machine Logic", "Home Tool Markup List", "Hyperlink Text Main Language"], 0),
]


def clean_chain_word(raw: str) -> str | None:
    word = sanitize_text(raw.strip().lower())
    if 2 <= len(word) <= 40 and word.replace("-", "").replace("'", "").isalpha() and is_safe_text(raw):
        return word
    return None


class PollView(discord.ui.View):
    def __init__(self, title: str, options: list[str], intro: str = "") -> None:
        super().__init__(timeout=900)
        self.title = title
        self.options = options
        self.intro = intro
        self.votes: dict[int, int] = {}
        for index, option in enumerate(options):
            self.add_item(PollButton(index, option[:80]))

    def embed(self) -> discord.Embed:
        total = max(len(self.votes), 1)
        lines = []
        for index, option in enumerate(self.options):
            count = list(self.votes.values()).count(index)
            pct = round(count / total * 100)
            lines.append(f"**{option}**\n{progress_bar(pct, 100, size=12)} `{count}` votes • `{pct}%`")
        body = "\n\n".join(lines)
        if self.intro:
            body = f"{soft_header(self.intro)}\n\n{body}"
        return base_embed(self.title, body)


class PollButton(discord.ui.Button):
    def __init__(self, index: int, label: str) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary if index == 0 else discord.ButtonStyle.secondary)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if not isinstance(view, PollView):
            return
        view.votes[interaction.user.id] = self.index
        await interaction.response.edit_message(embed=view.embed(), view=view)


class GuessLetterModal(discord.ui.Modal, title="Guess a letter or word"):
    guess = discord.ui.TextInput(label="Guess", min_length=1, max_length=30)

    def __init__(self, view: "HangmanView") -> None:
        super().__init__()
        self.hangman_view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.hangman_view.apply_guess(interaction, str(self.guess.value).strip().lower())


class HangmanView(discord.ui.View):
    def __init__(self, bot: commands.Bot, host_id: int, word: str, multiplayer: bool) -> None:
        super().__init__(timeout=1200)
        self.bot = bot
        self.host_id = host_id
        self.word = word
        self.multiplayer = multiplayer
        self.guessed: set[str] = set()
        self.bad = 0
        self.session_id = str(uuid.uuid4())

    def masked(self) -> str:
        return " ".join(char if char in self.guessed else "_" for char in self.word)

    def embed(self) -> discord.Embed:
        guessed = ", ".join(sorted(self.guessed)) or "None"
        danger = progress_bar(6 - self.bad, 6, size=6)
        return game_embed("🧩 Hangman", f"{soft_header('Guess the hidden word')}\n`{self.masked()}`\n\nLives: {danger} **{6 - self.bad}/6**\nGuessed: {guessed}")

    @discord.ui.button(label="Guess", emoji="🔤", style=discord.ButtonStyle.primary)
    async def guess_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self.multiplayer and interaction.user.id != self.host_id:
            await interaction.response.send_message("This solo Hangman round belongs to the host.", ephemeral=True)
            return
        await interaction.response.send_modal(GuessLetterModal(self))

    @discord.ui.button(label="End", emoji="🛑", style=discord.ButtonStyle.danger)
    async def end_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("Only the host can end this Hangman round.", ephemeral=True)
            return
        await self.bot.db.end_session(self.session_id)
        self.stop()
        await interaction.response.edit_message(embed=warning_embed("Hangman ended", f"The word was **{self.word}**."), view=None)

    async def apply_guess(self, interaction: discord.Interaction, guess: str) -> None:
        assert interaction.guild
        if not guess.isalpha() or not is_safe_text(guess):
            await interaction.response.send_message("Use clean letters only.", ephemeral=True)
            return
        if len(guess) == 1:
            if guess in self.guessed:
                await interaction.response.send_message("That letter was already guessed.", ephemeral=True)
                return
            self.guessed.add(guess)
            if guess not in self.word:
                self.bad += 1
        elif guess != self.word:
            self.bad += 1
        if guess == self.word or all(char in self.guessed for char in self.word):
            await self.bot.db.record_game_result(interaction.guild.id, interaction.user.id, "hangman", "win")
            await self.bot.db.add_coins(interaction.guild.id, interaction.user.id, 100)
            await self.bot.db.end_session(self.session_id)
            self.stop()
            await interaction.response.edit_message(embed=success_embed("Hangman solved", f"<@{interaction.user.id}> found **{self.word}** and earned **100 {COIN}**."), view=None)
            return
        if self.bad >= 6:
            await self.bot.db.end_session(self.session_id)
            self.stop()
            await interaction.response.edit_message(embed=warning_embed("Hangman lost", f"The word was **{self.word}**."), view=None)
            return
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def on_timeout(self) -> None:
        await self.bot.db.end_session(self.session_id)


class WordModal(discord.ui.Modal, title="Submit a word"):
    word = discord.ui.TextInput(label="Word", min_length=2, max_length=40)

    def __init__(self, view: "WordChainView") -> None:
        super().__init__()
        self.word_view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.word_view.submit_word(interaction, str(self.word.value).strip().lower())


class WordChainView(discord.ui.View):
    def __init__(self, bot: commands.Bot, host_id: int, starting_word: str) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.host_id = host_id
        self.last_word = starting_word
        self.used: list[str] = [starting_word]
        self.players: list[int] = []
        self.session_id = str(uuid.uuid4())

    def embed(self) -> discord.Embed:
        next_letter = self.last_word[-1].upper()
        recent = ", ".join(self.used[-8:])
        return game_embed("🔤 Word Chain", f"{soft_header('Keep the chain alive')}\nLast word: **{self.last_word}**\nNext word starts with **{next_letter}**.\n\n{section('Recent words', recent)}")

    @discord.ui.button(label="Submit Word", emoji="✍️", style=discord.ButtonStyle.primary)
    async def submit_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(WordModal(self))

    @discord.ui.button(label="End", emoji="🏁", style=discord.ButtonStyle.danger)
    async def end_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("Only the host can end this chain.", ephemeral=True)
            return
        assert interaction.guild
        for player_id in set(self.players):
            await self.bot.db.add_coins(interaction.guild.id, player_id, 25)
            await self.bot.db.record_game_result(interaction.guild.id, player_id, "wordchain", "draw")
        await self.bot.db.end_session(self.session_id)
        self.stop()
        await interaction.response.edit_message(embed=success_embed("Word Chain ended", f"Players earned **25 {COIN}** for joining the chain."), view=None)

    async def submit_word(self, interaction: discord.Interaction, word: str) -> None:
        cleaned = clean_chain_word(word)
        if not cleaned:
            await interaction.response.send_message("Use one clean word with letters only.", ephemeral=True)
            return
        word = cleaned
        if word in self.used:
            await interaction.response.send_message("That word has already been used.", ephemeral=True)
            return
        if word[0].lower() != self.last_word[-1].lower():
            await interaction.response.send_message(f"Your word must start with **{self.last_word[-1].upper()}**.", ephemeral=True)
            return
        self.last_word = sanitize_text(word)
        self.used.append(self.last_word)
        self.players.append(interaction.user.id)
        if interaction.guild and interaction.channel:
            await self.bot.db.save_session(
                self.session_id,
                interaction.guild.id,
                interaction.channel.id,
                "wordchain",
                {"last_word": self.last_word, "used": self.used[-25:], "host": self.host_id},
            )
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def on_timeout(self) -> None:
        await self.bot.db.end_session(self.session_id)


class QuestionModal(discord.ui.Modal):
    text = discord.ui.TextInput(label="Question or guess", min_length=2, max_length=100)

    def __init__(self, view: "TwentyQuestionsView", mode: str) -> None:
        super().__init__(title="Ask a question" if mode == "ask" else "Make a guess")
        self.questions_view = view
        self.mode = mode

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.questions_view.handle_text(interaction, str(self.text.value), self.mode)


class TwentyQuestionsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, host_id: int, target: str) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.host_id = host_id
        self.target = target
        self.asked = 0
        self.history: list[str] = []

    def embed(self) -> discord.Embed:
        history = "\n".join(self.history[-8:]) or "No questions yet."
        return game_embed("❓ 20 Questions", f"{soft_header('Ask yes/no clues, then make a guess')}\n{progress_bar(self.asked, 20, size=10)} **{self.asked}/20** questions\n\n{history}")

    @discord.ui.button(label="Ask", emoji="❔", style=discord.ButtonStyle.primary)
    async def ask(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(QuestionModal(self, "ask"))

    @discord.ui.button(label="Guess", emoji="🎯", style=discord.ButtonStyle.success)
    async def guess(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(QuestionModal(self, "guess"))

    async def handle_text(self, interaction: discord.Interaction, text: str, mode: str) -> None:
        assert interaction.guild
        clean = sanitize_text(text.lower())
        if mode == "guess":
            if self.target in clean:
                await self.bot.db.record_game_result(interaction.guild.id, interaction.user.id, "20questions", "win")
                await self.bot.db.add_coins(interaction.guild.id, interaction.user.id, 120)
                self.stop()
                await interaction.response.edit_message(embed=success_embed("Correct guess", f"The answer was **{self.target}**. <@{interaction.user.id}> earned **120 {COIN}**."), view=None)
                return
            self.history.append(f"Guess: {sanitize_text(text)} — No")
        else:
            self.asked += 1
            keywords = QUESTION_TARGETS[self.target]
            answer = "Yes" if any(word in clean for word in keywords) else random.choice(["No", "Probably not", "Not exactly"])
            self.history.append(f"Q{self.asked}: {sanitize_text(text)} — **{answer}**")
        if self.asked >= 20:
            self.stop()
            await interaction.response.edit_message(embed=warning_embed("20 Questions over", f"The answer was **{self.target}**."), view=None)
            return
        await interaction.response.edit_message(embed=self.embed(), view=self)


class TriviaButton(discord.ui.Button):
    def __init__(self, index: int, label: str) -> None:
        super().__init__(label=label[:80], style=discord.ButtonStyle.secondary, row=index // 2)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, TriviaView):
            await view.answer(interaction, self.index)


class TriviaView(discord.ui.View):
    def __init__(self, bot: commands.Bot, rounds: int) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.rounds = rounds
        self.index = 0
        self.scores: dict[int, int] = {}
        self.answered: set[int] = set()
        self.questions = random.sample(TRIVIA, k=min(rounds, len(TRIVIA)))
        self.load_buttons()

    def load_buttons(self) -> None:
        self.clear_items()
        _, options, _ = self.questions[self.index]
        for i, option in enumerate(options):
            self.add_item(TriviaButton(i, option))

    def embed(self, note: str | None = None) -> discord.Embed:
        question, _, _ = self.questions[self.index]
        scores = " • ".join(f"<@{uid}> {score}" for uid, score in self.scores.items()) or "No points yet."
        desc = f"{soft_header(f'Round {self.index + 1}/{len(self.questions)}')}\n**{question}**\n\n{section('Scores', scores)}"
        if note:
            desc += f"\n\n{note}"
        return game_embed("🌍 Global Trivia Battle", desc)

    async def answer(self, interaction: discord.Interaction, answer_index: int) -> None:
        assert interaction.guild
        if interaction.user.id in self.answered:
            await interaction.response.send_message("You already answered this round.", ephemeral=True)
            return
        self.answered.add(interaction.user.id)
        _, options, correct = self.questions[self.index]
        note = f"{interaction.user.mention} chose **{options[answer_index]}**."
        if answer_index == correct:
            self.scores[interaction.user.id] = self.scores.get(interaction.user.id, 0) + 1
            note += " Correct!"
        else:
            note += f" Correct answer: **{options[correct]}**."
        self.index += 1
        self.answered.clear()
        if self.index >= len(self.questions):
            if self.scores:
                top_score = max(self.scores.values())
                winners = [uid for uid, score in self.scores.items() if score == top_score]
                for uid in winners:
                    await self.bot.db.record_game_result(interaction.guild.id, uid, "trivia", "win")
                    await self.bot.db.add_coins(interaction.guild.id, uid, 130)
                winner_text = ", ".join(f"<@{uid}>" for uid in winners)
                self.stop()
                await interaction.response.edit_message(embed=success_embed("Trivia complete", f"Winners: {winner_text}\nEach earned **130 {COIN}**."), view=None)
                return
            await interaction.response.edit_message(embed=warning_embed("Trivia complete", "No answers were scored."), view=None)
            return
        self.load_buttons()
        await interaction.response.edit_message(embed=self.embed(note), view=self)


def random_ships() -> set[int]:
    return set(random.sample(range(25), 5))


class BattleCell(discord.ui.Button):
    def __init__(self, index: int) -> None:
        row, col = divmod(index, 5)
        super().__init__(label=f"{chr(65 + row)}{col + 1}", style=discord.ButtonStyle.secondary, row=row)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if isinstance(view, BattleshipView):
            await view.fire(interaction, self.index)


class BattleshipView(discord.ui.View):
    def __init__(self, bot: commands.Bot, players: list[int]) -> None:
        super().__init__(timeout=1200)
        self.bot = bot
        self.players = players
        self.turn = 0
        self.ships = {players[0]: random_ships(), players[1]: random_ships()}
        self.shots = {players[0]: set(), players[1]: set()}
        self.session_id = str(uuid.uuid4())
        for index in range(25):
            self.add_item(BattleCell(index))

    def current_user_id(self) -> int:
        return self.players[self.turn % 2]

    def target_user_id(self) -> int:
        return self.players[(self.turn + 1) % 2]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.players:
            await interaction.response.send_message("This Battleship board belongs to another match.", ephemeral=True)
            return False
        return True

    def public_grid(self, attacker_id: int) -> str:
        target_id = self.players[1] if attacker_id == self.players[0] else self.players[0]
        cells = []
        for index in range(25):
            if index not in self.shots[attacker_id]:
                cells.append("⬛")
            elif index in self.ships[target_id]:
                cells.append("🔥")
            else:
                cells.append("🌊")
        return "```\n" + "\n".join("".join(cells[i:i + 5]) for i in range(0, 25, 5)) + "\n```"

    def embed(self, note: str | None = None) -> discord.Embed:
        current = self.current_user_id()
        desc = f"{soft_header('5x5 tactical duel')}\nTurn: <@{current}> fires at <@{self.target_user_id()}>'s waters.\n\n{self.public_grid(current)}"
        if note:
            desc += f"\n\n{note}"
        return game_embed("🚢 Battleship", desc)

    async def fire(self, interaction: discord.Interaction, index: int) -> None:
        assert interaction.guild
        attacker = self.current_user_id()
        target = self.target_user_id()
        if interaction.user.id != attacker:
            await interaction.response.send_message("Wait for your turn.", ephemeral=True)
            return
        if index in self.shots[attacker]:
            await interaction.response.send_message("You already fired there.", ephemeral=True)
            return
        self.shots[attacker].add(index)
        hit = index in self.ships[target]
        if self.ships[target].issubset(self.shots[attacker]):
            await self.bot.db.record_game_result(interaction.guild.id, attacker, "battleship", "win")
            await self.bot.db.record_game_result(interaction.guild.id, target, "battleship", "loss")
            await self.bot.db.add_coins(interaction.guild.id, attacker, 180)
            await self.bot.db.add_coins(interaction.guild.id, target, 45)
            await self.bot.db.end_session(self.session_id)
            self.stop()
            await interaction.response.edit_message(embed=success_embed("Battleship victory", f"<@{attacker}> sank the fleet and earned **180 {COIN}**."), view=None)
            return
        self.turn += 1
        if interaction.channel:
            await self.bot.db.save_session(
                self.session_id,
                interaction.guild.id,
                interaction.channel.id,
                "battleship",
                {"players": self.players, "turn": self.turn, "shots": {str(k): sorted(v) for k, v in self.shots.items()}},
            )
        await interaction.response.edit_message(embed=self.embed("Hit!" if hit else "Miss."), view=self)

    async def on_timeout(self) -> None:
        await self.bot.db.end_session(self.session_id)


class AdditionalGames(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Start an interactive Would You Rather poll.")
    @app_commands.checks.cooldown(1, 8)
    async def wyr(self, interaction: discord.Interaction) -> None:
        left, right = random.choice(WYR_PROMPTS)
        view = PollView("🤔 Would You Rather", [left, right], "Vote with the buttons. You can change your vote.")
        await interaction.response.send_message(embed=view.embed(), view=view)

    @app_commands.command(description="Start an interactive Never Have I Ever poll.")
    @app_commands.checks.cooldown(1, 8)
    async def nhie(self, interaction: discord.Interaction) -> None:
        prompt = random.choice(NHIE_PROMPTS)
        view = PollView("🙋 Never Have I Ever", ["I have", "Never"], prompt)
        await interaction.response.send_message(embed=view.embed(), view=view)

    @app_commands.command(description="Play Hangman solo or with the channel.")
    @app_commands.checks.cooldown(1, 10)
    async def hangman(self, interaction: discord.Interaction, multiplayer: bool = True) -> None:
        assert interaction.guild and interaction.channel
        word = random.choice(HANGMAN_WORDS)
        view = HangmanView(self.bot, interaction.user.id, word, multiplayer)
        await self.bot.db.save_session(view.session_id, interaction.guild.id, interaction.channel.id, "hangman", {"word_length": len(word), "host": interaction.user.id})
        await interaction.response.send_message(embed=view.embed(), view=view)

    @app_commands.command(description="Play a 5x5 Battleship duel.")
    @app_commands.checks.cooldown(1, 15)
    async def battleship(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        assert interaction.guild and interaction.channel
        if opponent.bot or opponent.id == interaction.user.id:
            await interaction.response.send_message("Choose another human player.", ephemeral=True)
            return
        view = BattleshipView(self.bot, [interaction.user.id, opponent.id])
        await self.bot.db.save_session(view.session_id, interaction.guild.id, interaction.channel.id, "battleship", {"players": view.players})
        await interaction.response.send_message(content=opponent.mention, embed=view.embed(), view=view)

    @app_commands.command(description="Start a multilingual-friendly Word Chain round.")
    @app_commands.checks.cooldown(1, 10)
    async def wordchain(self, interaction: discord.Interaction, starting_word: str) -> None:
        assert interaction.guild and interaction.channel
        clean = clean_chain_word(starting_word)
        if not clean:
            await interaction.response.send_message("Pick a clean starting word with letters only.", ephemeral=True)
            return
        view = WordChainView(self.bot, interaction.user.id, clean)
        await self.bot.db.save_session(view.session_id, interaction.guild.id, interaction.channel.id, "wordchain", {"last_word": clean, "host": interaction.user.id})
        await interaction.response.send_message(embed=view.embed(), view=view)

    @app_commands.command(name="questions", description="Play 20 Questions against the bot.")
    @app_commands.checks.cooldown(1, 10)
    async def questions(self, interaction: discord.Interaction) -> None:
        target = random.choice(list(QUESTION_TARGETS))
        view = TwentyQuestionsView(self.bot, interaction.user.id, target)
        await interaction.response.send_message(embed=view.embed(), view=view)

    @app_commands.command(description="Start a global trivia battle.")
    @app_commands.describe(rounds="Number of trivia rounds")
    @app_commands.checks.cooldown(1, 12)
    async def trivia(self, interaction: discord.Interaction, rounds: app_commands.Range[int, 1, 4] = 4) -> None:
        view = TriviaView(self.bot, rounds)
        await interaction.response.send_message(embed=view.embed(), view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdditionalGames(bot))
