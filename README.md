# Sweater

The daily NHL player guessing game. 

Sweater is a fan-made game and is not affiliated with or endorsed by the NHL or its teams.

## How it runs

A GitHub Actions workflow (`.github/workflows/update.yml`) runs every day. It:

1. pulls current rosters, games played and career history from the NHL's public web API,
2. keeps `schedule.json` up to date (a fixed list of daily mystery players; past days and tomorrow never change),
3. builds `site/index.html` and publishes it with GitHub Pages.

## Files

| File | What it is |
| --- | --- |
| `build_sweater.py` | Builds the game. Also runs on Windows with `Run Sweater.bat`. |
| `og-image.png` | The preview image shown when the link is shared. |
| `schedule.json` | Created automatically. Don't edit or delete it, or past daily answers change. |
| `career_cache.json` | Created automatically. Saves career history so updates are faster. |

## Settings

- **Settings → Pages → Source:** GitHub Actions
- **Settings → Secrets and variables → Actions → Variables:** `SITE_URL` = your site address, e.g. `https://playsweater.com/`

To rebuild right away: **Actions → Update Sweater → Run workflow**.
