# PartyGames Bot Server Guide

PartyGames Bot is a slash-command Discord bot for safe multiplayer party games, Vibe Coins, profiles, leaderboards, and interactive button-based games.

## Add The Bot To Your Server

Ask the bot owner for the invite link, or use `/invite` in a server where the bot is already installed.

When inviting, make sure these scopes are selected:

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

After inviting the bot, run:

```text
/setup
/help
```

## How To Use Commands

This bot uses **slash commands only**.

Type `/` in Discord, then search for a command like:

```text
/tod start
/tictactoe
/connect4
/daily
```

Most games use buttons after the command starts.

## Main Games

### Truth Or Dare

Start a group session:

```text
/tod start
```

Optional:

```text
/tod start rounds:5 category:Fun
```

Players can press:

- `Join`
- `Spin Bottle`
- `Truth`
- `Dare`
- `Custom Truth`
- `Custom Dare`
- `Skip`
- `End Game`

The bottle chooses the next player. Custom prompts are filtered for safety.

Single prompts:

```text
/truth
/dare
```

Anonymous truth:

```text
/truth anonymous:True
```

### Tic Tac Toe

Play against the bot:

```text
/tictactoe
```

Play against a servermate:

```text
/tictactoe opponent:@friend
```

Optional:

```text
/tictactoe opponent:@friend best_of:Best of 5
```

### Connect 4

Challenge another player:

```text
/connect4 opponent:@friend
```

Players take turns pressing column buttons.

### Rock Paper Scissors

Play against the bot:

```text
/rps
```

Play against another player:

```text
/rps opponent:@friend
```

### Battleship

Start a 1v1 Battleship match:

```text
/battleship opponent:@friend
```

### Hangman

Start Hangman:

```text
/hangman
```

Solo mode:

```text
/hangman multiplayer:False
```

### Word Chain

Start a word chain:

```text
/wordchain starting_word:party
```

Players submit words using buttons and modals.

### 20 Questions

Play against the bot:

```text
/questions
```

Ask questions and guess the hidden answer.

### Trivia

Start a trivia battle:

```text
/trivia
```

Optional:

```text
/trivia rounds:4
```

### Would You Rather

```text
/wyr
```

### Never Have I Ever

```text
/nhie
```

## Economy And Profiles

Claim daily Vibe Coins:

```text
/daily
```

View your profile:

```text
/profile
```

View another member:

```text
/profile member:@friend
```

View leaderboards:

```text
/leaderboard board:Most wins
/leaderboard board:Most coins
/leaderboard board:Highest level
```

Open the shop:

```text
/shop
```

Buy an item:

```text
/buy item:Funny title
```

## Lobbies

Create a private game thread:

```text
/lobby create game:Truth or Dare
```

This is useful for keeping game messages out of general chat.

## Safety Features

PartyGames Bot is designed for age-appropriate servers.

Included safety tools:

- Profanity and unsafe-content filter
- Report buttons
- `/report`
- Cooldowns to reduce spam
- Moderator game bans
- Safe Truth or Dare categories

Report a user or issue:

```text
/report reason:explain the issue member:@user
```

Moderator game ban:

```text
/gameban member:@user banned:True
```

Unban:

```text
/gameban member:@user banned:False
```

Reset a member's coins:

```text
/resetcoins member:@user
```

## Recommended Server Setup

Create channels like:

```text
#party-games
#bot-commands
#game-lobbies
```

Then use:

```text
/lobby create game:Game Name
```

Recommended first commands:

```text
/setup
/help
/daily
/tod start
/tictactoe
/connect4
```

## Troubleshooting

### Commands Do Not Show Up

Try:

```text
/help
```

If commands still do not appear:

- Wait up to 1 hour for Discord global slash command sync.
- Make sure the bot was invited with `applications.commands`.
- Ask the bot owner to restart the bot.

### Bot Does Not Reply

Check that the bot has:

- View Channels
- Send Messages
- Embed Links
- Read Message History

### Lobby Creation Fails

The bot needs:

- Create Private Threads
- Manage Threads

### Coins Or Stats Reset

The bot owner must make sure the SQLite database file is stored persistently:

```text
data/partygames.sqlite3
```

## Quick Command List

```text
/help
/setup
/invite
/truth
/dare
/tod start
/tictactoe
/connect4
/rps
/wyr
/nhie
/hangman
/battleship
/wordchain
/questions
/trivia
/daily
/profile
/leaderboard
/shop
/buy
/randomgame
/lobby create
/report
/gameban
/resetcoins
```
