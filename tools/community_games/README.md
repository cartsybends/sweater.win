# Sweater Grid, Bench Boss, and Teammate Trail

`static/community-games/data.json` is an immutable puzzle bank. Normal builds
schedule its IDs and embed the same rules/data used by the leaderboard worker.
Keep published puzzle IDs and their answers unchanged so saved runs and archives
continue to work. Add new puzzles with new IDs when expanding the bank.

Sources are the official NHL summary/bios APIs and `team_history_cache.json`.
The bank records source hashes and its snapshot date. Player appearances cover
current clubs through 2025–26; predecessor clubs are separate. Career GP, birth
country/year, primary position, and Hall of Fame membership come from NHL bios.
Dual-role emergency goalies use their primary record, without duplicating GP.

Bench Boss uses full league-wide totals, including retired franchises and trades,
for completed seasons from 2005–06 through 2024–25. `season_totals.json` stores
compact official summaries and the hashes of all 40 unmodified source responses.
Cards contain `[id, credits, points, goals, assists, wins, club, GP, position]`.
Their club identifies the largest stint at a current club in that season;
scoring uses the player's entire NHL season. Each market has an exact optimum
for three forwards, two defensemen, one goalie, and at most 100 credits.

Teammate links require guaranteed shared regular-season appearances. In the
included era (1967 onward), no season has more than 84 games. Two club-season
GP totals whose sum is at least 89 therefore guarantee five shared appearances,
even when either player was traded. Links store the club, year, and both GP
totals. This is a conservative verified subset of real teammate relationships;
the game offers/searches only those verified links. Stored solutions are shortest
paths in this graph.

Grid squares each have at least nine candidates, so eight distinct answers can
never leave the final square without an unused valid player. Short-stint bonuses
come from qualifying club GP, rather than invented answer-popularity figures.

Run the checks from the repository root:

```sh
node tests/community_games.mjs
python -B tests/community_games_data.py
```

The Python oracle checks official season totals and teammate overlap, and uses
an independent knapsack DP to verify every market optimum. JavaScript checks
all boards, shortest routes, replay validation, and browser/server score parity.

For initial curation, download unmodified `skater-bios.json`, `goalie-bios.json`,
and aggregate regular-season `{skater,goalie}-{2005..2024}.json` responses into
private input directories. `build_data.py --bios-dir ... --league-dir ... --out ...`
produces a deterministic bank. `--replace-bank` is for unpublished IDs only;
do not regenerate an already published bank in place.
