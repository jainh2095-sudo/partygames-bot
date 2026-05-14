from __future__ import annotations

import asyncio
import random
import uuid

import discord
from discord import app_commands
from discord.ext import commands

from utils.constants import BRAND_PINK, COIN, SHIELD
from utils.embeds import base_embed, game_embed, soft_header, success_embed, warning_embed
from utils.safety import is_safe_text, sanitize_text


CATEGORIES = ["Safe", "Fun", "Chaotic", "Deep", "International"]

TRUTHS = {
    "Safe": [
        "What song instantly puts you in a good mood?",
        "What is a tiny thing that makes your day better?",
        "What skill would you learn overnight if you could?",
    ],
    "Fun": [
        "What is the funniest nickname someone has given you?",
        "Which fictional world would you visit for one weekend?",
        "What harmless thing are you weirdly competitive about?",
    ],
    "Chaotic": [
        "If your last three emojis became your squad, what is the story?",
        "What is your most dramatic reaction to a minor inconvenience?",
        "What app would expose your personality the fastest?",
    ],
    "Deep": [
        "What compliment has stayed with you for a long time?",
        "What do you wish more people understood about you?",
        "What is a small goal you are proud of keeping alive?",
    ],
    "International": [
        "What food from your country should everyone try once?",
        "What word in your language has no perfect English translation?",
        "What local tradition feels normal to you but surprises others?",
    ],
}

DARES = {
    "Safe": [
        "Send a wholesome compliment to the player above you.",
        "Change your nickname for 10 minutes to a fruit plus your favorite color.",
        "React to the last five messages with only positive energy.",
    ],
    "Fun": [
        "Describe your day using only movie titles.",
        "Type a sentence without using the letter E.",
        "Make a dramatic weather report for the current chat vibe.",
    ],
    "Chaotic": [
        "Let the group pick your profile title for the next round.",
        "Speak like a game show host for your next two messages.",
        "Invent a fake holiday and convince everyone it matters.",
    ],
    "Deep": [
        "Share one thing you are grateful for this week.",
        "Give genuine advice you wish someone gave you earlier.",
        "Name one friend quality you value and tag someone who has it.",
    ],
    "International": [
        "Teach everyone a friendly phrase from another language.",
        "Recommend a song from outside your country.",
        "Describe your city using only three emojis and one sentence.",
    ],
}

SPIN_FRAMES = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"]


def category_choice(category: str | None) -> str:
    if not category:
        return "Safe"
    return category if category in CATEGORIES else "Safe"


class ReportButton(discord.ui.Button):
    def __init__(self, target_user_id: int | None = None) -> None:
        super().__init__(label="Report", emoji=SHIELD, style=discord.ButtonStyle.danger, custom_id="tod:report")
        self.target_user_id = target_user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        assert interaction.guild
        await interaction.client.db.add_report(
            interaction.guild.id,
            interaction.user.id,
            "Truth or Dare prompt or interaction reported",
            self.target_user_id,
            interaction.message.id if interaction.message else None,
        )
        await interaction.response.send_message(
            embed=success_embed("Report received", "A server moderator can review this from the bot database."),
            ephemeral=True,
        )


class PromptView(discord.ui.View):
    def __init__(self, target_user_id: int | None = None) -> None:
        super().__init__(timeout=None)
        self.add_item(ReportButton(target_user_id))


class CustomPromptModal(discord.ui.Modal):
    prompt = discord.ui.TextInput(
        label="Your custom prompt",
        placeholder="Keep it safe, age-appropriate, and server-friendly.",
        min_length=5,
        max_length=180,
        style=discord.TextStyle.paragraph,
    )

    def __init__(self, view: "TODSessionView", kind: str) -> None:
        super().__init__(title=f"Custom {kind}")
        self.session_view = view
        self.kind = kind

    async def on_submit(self, interaction: discord.Interaction) -> None:
        text = str(self.prompt.value).strip()
        await self.session_view.handle_custom_prompt(interaction, self.kind, text)


class TODSessionView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        session_id: str,
        players: list[int],
        rounds: int,
        category: str,
        *,
        current_round: int = 1,
        turn_index: int = 0,
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.session_id = session_id
        self.players = players
        self.rounds = rounds
        self.category = category
        self.current_round = current_round
        self.turn_index = turn_index

    @property
    def current_player_id(self) -> int:
        return self.players[self.turn_index % len(self.players)]

    def spin_bottle(self) -> int:
        if len(self.players) <= 1:
            self.turn_index = 0
            return self.current_player_id
        current = self.current_player_id
        choices = [player_id for player_id in self.players if player_id != current]
        chosen = random.choice(choices or self.players)
        self.turn_index = self.players.index(chosen)
        return chosen

    def spin_embed(self, guild: discord.Guild, frame: str, tick: int) -> discord.Embed:
        names = []
        for index, player_id in enumerate(self.players, start=1):
            member = guild.get_member(player_id)
            names.append(f"`{index}` {member.display_name if member else f'User {player_id}'}")
        description = (
            f"{soft_header('Bottle spinning')}\n"
            f"Round **{self.current_round}/{self.rounds}**\n\n"
            f"# {frame} 🍾\n\n"
            f"Players:\n" + "\n".join(names)
        )
        embed = game_embed("🎭 Spin the Bottle", description)
        embed.add_field(name="Choosing", value="The bottle is finding the next player...", inline=False)
        embed.set_footer(text=f"Spin energy {'•' * ((tick % 3) + 1)}")
        return embed

    async def animate_spin(self, interaction: discord.Interaction) -> None:
        assert interaction.guild
        frames = SPIN_FRAMES + random.sample(SPIN_FRAMES, k=4)
        await interaction.response.edit_message(embed=self.spin_embed(interaction.guild, frames[0], 0), view=None)
        for tick, frame in enumerate(frames[1:], start=1):
            await asyncio.sleep(0.32 + min(tick * 0.025, 0.16))
            await interaction.edit_original_response(embed=self.spin_embed(interaction.guild, frame, tick), view=None)
        self.spin_bottle()
        await self.save(interaction)
        await asyncio.sleep(0.35)
        await interaction.edit_original_response(embed=self.prompt_embed(interaction.guild), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.players:
            await interaction.response.send_message("Only players in this session can press these buttons.", ephemeral=True)
            return False
        return True

    def prompt_embed(
        self,
        guild: discord.Guild,
        kind: str | None = None,
        prompt: str | None = None,
        *,
        prompt_target_id: int | None = None,
    ) -> discord.Embed:
        member = guild.get_member(self.current_player_id)
        mention = member.mention if member else f"<@{self.current_player_id}>"
        description = f"{soft_header('Spin the bottle session')}\nRound **{self.current_round}/{self.rounds}**\nBottle landed on: {mention}\nCategory: **{self.category}**"
        if kind and prompt:
            target_id = prompt_target_id or self.current_player_id
            target = guild.get_member(target_id)
            target_mention = target.mention if target else f"<@{target_id}>"
            description += f"\n\n**{kind} for {target_mention}:**\n> {sanitize_text(prompt)}"
        embed = game_embed("🎭 Truth or Dare", description, current=member)
        embed.add_field(name="Controls", value="`Spin Bottle` chooses the player. Use bot prompts or custom safe prompts.", inline=False)
        return embed

    async def save(self, interaction: discord.Interaction) -> None:
        assert interaction.guild and interaction.channel
        await self.bot.db.save_session(
            self.session_id,
            interaction.guild.id,
            interaction.channel.id,
            "truth_or_dare",
            {
                "players": self.players,
                "rounds": self.rounds,
                "category": self.category,
                "current_round": self.current_round,
                "turn_index": self.turn_index,
            },
        )

    async def next_turn(self, interaction: discord.Interaction, final_embed: discord.Embed | None = None) -> bool:
        if self.current_round >= self.rounds:
            for player_id in self.players:
                await self.bot.db.add_coins(interaction.guild.id, player_id, 35)
                await self.bot.db.record_game_result(interaction.guild.id, player_id, "truth_or_dare", "draw")
            await self.bot.db.end_session(self.session_id)
            self.stop()
            if final_embed:
                final_embed.add_field(name="Session complete", value=f"Everyone earned **35 {COIN}** for finishing.", inline=False)
            await interaction.response.edit_message(
                embed=final_embed or success_embed("Truth or Dare complete", f"Everyone earned **35 {COIN}** for finishing the session."),
                view=None,
            )
            return True
        self.current_round += 1
        self.spin_bottle()
        await self.save(interaction)
        return False

    async def handle_pick(self, interaction: discord.Interaction, kind: str) -> None:
        if interaction.user.id != self.current_player_id:
            await interaction.response.send_message("It is not your turn yet.", ephemeral=True)
            return
        pool = TRUTHS if kind == "Truth" else DARES
        prompt = random.choice(pool[self.category])
        target_id = self.current_player_id
        final_embed = self.prompt_embed(interaction.guild, kind, prompt, prompt_target_id=target_id)
        if await self.next_turn(interaction, final_embed):
            return
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.prompt_embed(interaction.guild, kind, prompt, prompt_target_id=target_id), view=self)

    async def handle_custom_prompt(self, interaction: discord.Interaction, kind: str, prompt: str) -> None:
        assert interaction.guild
        if interaction.user.id not in self.players:
            await interaction.response.send_message("Only players in this session can submit custom prompts.", ephemeral=True)
            return
        if not is_safe_text(prompt):
            await self.bot.db.add_report(
                interaction.guild.id,
                interaction.user.id,
                f"Filtered custom {kind.lower()} prompt submitted",
                self.current_player_id,
                interaction.message.id if interaction.message else None,
            )
            await interaction.response.send_message("That prompt was blocked by the safety filter. Keep it friendly and age-appropriate.", ephemeral=True)
            return
        clean_prompt = sanitize_text(prompt)
        target_id = self.current_player_id
        asker = interaction.user.mention
        target = interaction.guild.get_member(target_id)
        decorated = f"{clean_prompt}\n\nAsked by {asker} for {target.mention if target else f'<@{target_id}>'}"
        final_embed = self.prompt_embed(interaction.guild, f"Custom {kind}", decorated, prompt_target_id=target_id)
        if await self.next_turn(interaction, final_embed):
            return
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.prompt_embed(interaction.guild, f"Custom {kind}", decorated, prompt_target_id=target_id), view=self)

    @discord.ui.button(label="Spin Bottle", emoji="🍾", style=discord.ButtonStyle.secondary, custom_id="tod:spin")
    async def spin(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if len(self.players) < 2:
            await interaction.response.send_message("At least two players should join before spinning the bottle.", ephemeral=True)
            return
        await self.animate_spin(interaction)

    @discord.ui.button(label="Truth", emoji="💬", style=discord.ButtonStyle.primary, custom_id="tod:truth")
    async def truth(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.handle_pick(interaction, "Truth")

    @discord.ui.button(label="Dare", emoji="⚡", style=discord.ButtonStyle.success, custom_id="tod:dare")
    async def dare(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.handle_pick(interaction, "Dare")

    @discord.ui.button(label="Custom Truth", emoji="✍️", style=discord.ButtonStyle.primary, custom_id="tod:custom_truth", row=1)
    async def custom_truth(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(CustomPromptModal(self, "Truth"))

    @discord.ui.button(label="Custom Dare", emoji="🎲", style=discord.ButtonStyle.success, custom_id="tod:custom_dare", row=1)
    async def custom_dare(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(CustomPromptModal(self, "Dare"))

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="tod:skip")
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.current_player_id:
            await interaction.response.send_message("Only the current player can skip.", ephemeral=True)
            return
        if await self.next_turn(interaction):
            return
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.prompt_embed(interaction.guild), view=self)

    @discord.ui.button(label="End Game", emoji="🛑", style=discord.ButtonStyle.danger, custom_id="tod:end")
    async def end(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self.bot.db.end_session(self.session_id)
        self.stop()
        await interaction.response.edit_message(embed=warning_embed("Session ended", "The group Truth or Dare session was ended."), view=None)


class TruthOrDare(commands.Cog):
    tod = app_commands.Group(name="tod", description="Group Truth or Dare sessions")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def category_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return [app_commands.Choice(name=c, value=c) for c in CATEGORIES if current.lower() in c.lower()][:25]

    @app_commands.command(description="Get a safe Truth prompt.")
    @app_commands.autocomplete(category=category_autocomplete)
    @app_commands.checks.cooldown(1, 5)
    async def truth(self, interaction: discord.Interaction, category: str | None = None, anonymous: bool = False) -> None:
        picked = category_choice(category)
        prompt = sanitize_text(random.choice(TRUTHS[picked]))
        title = "💬 Anonymous Truth" if anonymous else "💬 Truth"
        embed = base_embed(title, f"{soft_header(f'{picked} category')}\n> {prompt}", color=BRAND_PINK)
        await interaction.response.send_message(embed=embed, view=PromptView(interaction.user.id), ephemeral=anonymous)

    @app_commands.command(description="Get a safe Dare prompt.")
    @app_commands.autocomplete(category=category_autocomplete)
    @app_commands.checks.cooldown(1, 5)
    async def dare(self, interaction: discord.Interaction, category: str | None = None) -> None:
        picked = category_choice(category)
        prompt = sanitize_text(random.choice(DARES[picked]))
        embed = base_embed("⚡ Dare", f"{soft_header(f'{picked} category')}\n> {prompt}", color=BRAND_PINK)
        await interaction.response.send_message(embed=embed, view=PromptView(interaction.user.id))

    @tod.command(name="start", description="Start a multiplayer Truth or Dare session in this channel.")
    @app_commands.describe(rounds="Total rounds, 1-20", category="Prompt category")
    @app_commands.autocomplete(category=category_autocomplete)
    @app_commands.checks.cooldown(1, 15)
    async def tod_start(self, interaction: discord.Interaction, rounds: app_commands.Range[int, 1, 20] = 5, category: str | None = None) -> None:
        assert interaction.guild and interaction.channel
        picked = category_choice(category)
        players = [interaction.user.id]
        session_id = str(uuid.uuid4())
        view = TODSessionView(self.bot, session_id, players, rounds, picked)
        await self.bot.db.save_session(
            session_id,
            interaction.guild.id,
            interaction.channel.id,
            "truth_or_dare",
            {"players": players, "rounds": rounds, "category": picked, "current_round": 1, "turn_index": 0},
        )
        view.add_item(JoinTODButton(players))
        await interaction.response.send_message(embed=view.prompt_embed(interaction.guild), view=view)


class JoinTODButton(discord.ui.Button):
    def __init__(self, players: list[int]) -> None:
        super().__init__(label="Join", emoji="🙋", style=discord.ButtonStyle.secondary, custom_id="tod:join")
        self.players = players

    async def callback(self, interaction: discord.Interaction) -> None:
        parent = self.view
        if not isinstance(parent, TODSessionView):
            return
        if interaction.user.id in self.players:
            await interaction.response.send_message("You are already in this session.", ephemeral=True)
            return
        self.players.append(interaction.user.id)
        await parent.save(interaction)
        await interaction.response.edit_message(embed=parent.prompt_embed(interaction.guild), view=parent)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TruthOrDare(bot))
