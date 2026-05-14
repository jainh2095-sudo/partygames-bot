# PartyGames Bot

A slash-command Discord party games bot built with `discord.py` 2.x, app commands, buttons, embeds, and SQLite.

## Add to Discord servers

Server owners need an invite link with these scopes:

- `bot`
- `applications.commands`

Recommended permissions:

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Create Private Threads
- Manage Threads
- Use External Emojis

After configuring `.env`, generate an invite link:

```bash
python scripts/generate_invite.py
```

Once the bot is invited to a server, run:

- `/setup` for the admin checklist
- `/help` for commands
- `/invite` to share the bot invite link

Full hosting instructions are in `DEPLOYMENT.md`.

## Quick start

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and add your Discord bot token plus application ID.
4. Message Content intent is not required for the current slash-command/modal implementation.
5. Run the bot:

```bash
python bot.py
```

## Included

- `/truth`, `/dare`, `/tod start`
- `/tictactoe`
- `/connect4`
- `/rps`
- `/wyr`, `/nhie`
- `/hangman`
- `/battleship`
- `/wordchain`
- `/questions`
- `/trivia`
- `/daily`, `/profile`, `/leaderboard`, `/shop`, `/buy`
- `/randomgame`, `/help`, `/report`
- `/gameban`, `/resetcoins` for moderators

## Notes

This project stores guild-scoped data in SQLite through `aiosqlite`. Live button sessions are kept in memory and mirrored into a `game_sessions` table so the bot can mark interrupted sessions after restarts and keep history.

## Extend the bot

- Add new games as cogs in `cogs/`.
- Use `Database.save_session()` for live game state and `record_game_result()` for stats.
- Use `utils.embeds` for consistent visual style: branded author/footer, progress bars, section headers, and leaderboard rank labels.
- Use `utils.safety.sanitize_text()` before showing user-supplied text.
