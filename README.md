# rdm-steam-game

Pick a random game from the Steam store — directly from your terminal.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

`random-steam-game` scrapes the Steam store search index, selects a random title, and validates it against the Steam API to ensure it's a real, released, playable game — skipping demos, betas, prologues, and unreleased titles.

## Installation

```bash
git clone https://github.com/joao/rdm-steam-game.git
cd rdm-steam-game
uv sync
```

## Usage

```bash
rdm-steam-game
```

### Options

| Flag | Description |
| --- | --- |
| `--nsfw` | Include mature-rated games in the pool |
| `--nsfw-only` | Restrict selection to NSFW-tagged games only |

### Example output

```
============================================================
  Celeste
============================================================
  App ID:       504230
  Developer(s): Extremely OK Games, Ltd.
  Publisher(s): Extremely OK Games, Ltd.
  Release date: 25 Jan, 2018
  Price:        $19.99
  Genre(s):     Action, Indie, Platformer
  URL:          https://store.steampowered.com/app/504230/
============================================================
```

## How it works

1. Queries the Steam store search endpoint to get the total game count.
2. Picks a random page offset and fetches 100 results.
3. Selects one random entry from the page.
4. Calls the `appdetails` API to validate the title is a released, full game.
5. If the candidate is skipped (demo, unreleased, no platform, etc.), retries with a new pick — up to 30 attempts.

Rate-limit responses (HTTP 429) are handled automatically with exponential back-off.

## License

MIT
