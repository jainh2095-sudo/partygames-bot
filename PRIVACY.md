# Privacy Policy

PartyGames Bot stores only the data needed to run safe multiplayer games and progression.

## Stored data

- Discord guild IDs
- Discord user IDs
- Vibe Coin balances
- Levels, XP, daily streaks, and profile titles
- Game stats and session state
- Safety reports submitted with `/report` or report buttons
- Shop purchase records

## Not stored

- Bot tokens
- Private messages
- Message history outside submitted game/report content
- Payment information

## Data location

Data is stored in the host's SQLite database at `DATABASE_PATH`, defaulting to `data/partygames.sqlite3`.

## Data removal

Server operators can reset some user data with moderator commands. Host operators can remove guild data directly from SQLite if a server requests deletion.
