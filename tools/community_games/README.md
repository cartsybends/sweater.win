# Sweater Grid, Bench Boss, and Teammate Trail

`static/community-games/data.json` is an immutable puzzle bank. Normal builds
schedule its IDs and embed the same rules/data used by the leaderboard worker.
Keep published puzzle IDs, clues and historical records unchanged so saved runs
and archives continue to work. Add new puzzles with new IDs when expanding the bank.

Sources are the official NHL summary/bios APIs and `team_history_cache.json`.
The bank records source hashes and its snapshot date. Player appearances cover
current clubs through 2025–26; predecessor clubs are separate. Career GP, birth
country/year, primary position, and Hall of Fame membership come from NHL bios.
Dual-role emergency goalies use their primary record, without duplicating GP.

Grid also uses `grid_current_cache.json`, refreshed before each daily deployment
by `python -B tools/community_games/refresh_grid.py`. Official regular-season
summaries extend club appearances beyond the historical cutoff; trade-season
game logs verify the exact split between clubs. Current bios update career GP
and supply rookies. A roster assignment alone never establishes eligibility.
The cache records source URLs, response hashes and the verified date, and validates
all additions before replacing the previous snapshot. Browser search, answer
checking, server scoring and popularity validation use the same Grid catalog.
Bench Boss markets and the verified Teammate Trail graph retain their original data.

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
come from qualifying club GP while answer-popularity samples are still small.

`award_winners.json` contains 749 historical winner records, cross-checked
against all 432 records in the site's existing trophy history. The 48 appended
Grid boards use Hart, Vezina, Calder, and Lady Byng clues. A winner can qualify
for a team they played for at any point; they need not have won the trophy with
that club. `expand_grid.py` appends new IDs and keeps earlier puzzles intact.
Shared Vezina awards include every recipient, and same-name players are
disambiguated by their careers rather than a name-only match.
`original_bank_hashes.json` protects the originally published definitions and
player snapshot in CI without relying on a full Git history checkout.

`grid_achievements.json` adds official NHL Stanley Cup winner records and
complete player-season summaries from 1917–18 through 2025–26. Cup membership
uses individual WINNER records, supplemented by the NHL's explicitly engraved
player lists for recent seasons; sharing a roster with champions is insufficient.
Player award responses independently cross-check recent champions and negative
cases such as Roberto Luongo's executive wins. The 30-goal clue counts one NHL
regular season across all clubs, including trades and predecessor franchises.
Compact evidence rows and original response checksums are retained. Goal totals
are independently compared with the 20 complete league-season snapshots.
`expand_achievements.py --input-dir ...` appends 48 new IDs using these clues;
each new square still has at least nine valid answers. All 168 earlier Grid
definitions and the original player catalog remain protected and unchanged.

Grid popularity is collected separately from usage diagnostics. It records only
server-validated correct answers from finished daily/unlimited runs. Revealed
solutions, wrong guesses, and archive replays are excluded. A keyed hash replaces
the anonymous browser ID; one browser contributes at most one answer to each
canonical intersection during the 365-day retention window. Requests have
origin, size, and rate limits, and respect analytics opt-out, DNT, and GPC.

An intersection needs 100 anonymous answers before popularity affects bonuses:
at most 1% chosen earns +5, at most 5% +3, at most 10% +2, below 20% +1,
and 20% or more +0. Correct answers always earn the base 10 points. Until then,
the original short-stint bonuses apply. Upcoming daily references store their
own immutable rarity snapshot; unlimited runs persist theirs in saved options.
New samples affect future puzzles, rather than changing scores mid-game or in
archives. The website build refreshes `grid_popularity.json` from the public
aggregate endpoint and retains the previous snapshot during outages.

The 32 local crests and four flags are local vector files. Their manifests
include original URLs and SHA-256 checksums, verified during builds. The USA
flag uses smaller, explicitly drawn stars so its canton stays clear at Grid
icon sizes; this adaptation is recorded in the flag manifest. The other
vectors retain their source artwork. CSS adjusts their painted dimensions
rather than rasterizing scaled thumbnails.

Run the checks from the repository root:

```sh
node tests/community_games.mjs
node tests/grid_popularity.mjs
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
