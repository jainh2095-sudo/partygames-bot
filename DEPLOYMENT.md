# Deploy PartyGames Bot

This guide is for hosting the bot so Discord servers can invite and use it.

## 1. Create the Discord application

1. Go to the Discord Developer Portal.
2. Create an application named `PartyGames Bot`.
3. Open **Bot** and create a bot user.
4. Copy the bot token into `.env` as `DISCORD_TOKEN`.
5. Open **General Information** and copy the Application ID into `.env` as `APPLICATION_ID`.

Required scopes:

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

## 2. Configure `.env`

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Then set:

```env
DISCORD_TOKEN=your-bot-token
APPLICATION_ID=your-application-id
DATABASE_PATH=data/partygames.sqlite3
LOG_LEVEL=INFO
```

`PUBLIC_INVITE_URL` is optional. If omitted, `/invite` generates one automatically.

## 3. Run with Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

On Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## 4. Run with Docker

```bash
docker compose up -d --build
```

Logs:

```bash
docker compose logs -f
```

Stop:

```bash
docker compose down
```

The SQLite database is stored in `./data` and mounted into the container.

## 5. Add the bot to a server

After the bot starts, run `/invite` in any server where the bot is already present, or generate the invite from the Developer Portal with the scopes and permissions above.

After inviting:

1. Run `/setup`.
2. Run `/help`.
3. Try `/daily`, `/tod start`, `/tictactoe`, and `/connect4`.

## 6. Production notes

- Keep `.env` private.
- Back up `data/partygames.sqlite3`.
- Use one running bot process per database file.
- Restart the bot after changing cogs or dependencies.
- Slash command changes can take a little time to appear globally.
