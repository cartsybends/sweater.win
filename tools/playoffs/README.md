# Playoff Picture

The public route is `/#playoffs`. The tool consumes `playoffs_cache.json`,
embedded at build time and fetched from the public main branch every two minutes
while visible. It preserves the last validated forecast on an error. Shared links
freeze the selected team's stats and probabilities at the original forecast time.
PNG sharing includes the Sweater S mark, URL, timestamp, and model-estimate label.

## Refreshing

```sh
python -m pip install -r tools/playoffs/requirements.txt
python -B tools/playoffs/data.py
python -B tests/playoffs_data.py
node tests/playoffs.mjs
```

`refresh-playoffs.yml` checks every five minutes using GitHub Actions, whose
scheduler can run late. This is a postgame forecast, not an in-game model or a
guaranteed real-time service. Every check fetches the 32 official club schedules
and official standings. GP, points, RW, ROW, wins, GF and GA must agree exactly.
Conflicting or incomplete data fails the job and preserves the published file.
No forecast is published using a mixture of old standings and new results.

Historical schedules are cached only after all games are final and each club's
full schedule is present. The regular-season length is read/validated for the
season: 84 from 2026–27, 82 for the historical evaluation seasons. Preseason and
postseason games never enter regular-season points or strength training.

Unchanged results update `checked_at`, preserving `updated_at`, probabilities,
and history. Changes to the confirmed results, schedule, parameters, or model
produce a new forecast. The atomic file replacement occurs after conservation
and range checks. Data-only commits use `[skip ci]` and don't rebuild the site or
redeploy the API Worker. No new service, paid data feed, secret, database, or
betting provider is needed.

## Model v1 (beta)

This is an independent Sweater forecast, not the NHL's or a sportsbook's odds.
Scoring and goals allowed use gamma-Poisson posterior rates. The prior blends
the previous three regular seasons (60/30/10 weighting), regresses toward league
scoring, and is combined with current-season totals. Home advantage multiplies
home scoring and divides away scoring. Each simulated season draws attack and
defense rates once, preserving uncertainty about team strength across games.
Future simulated results do not retrain team strength inside a run.

Each remaining game draws Poisson scores. Ties are resolved by goal-rate-weighted
overtime, with an empirically estimated fraction resolved by shootout. Winners
receive 2 points and overtime/shootout losers receive 1. RW, ROW, total wins,
goals, and head-to-head results are maintained. Shootout wins add one awarded
goal to the winner, matching NHL standings treatment.

Seeding uses points, RW, ROW, wins, head-to-head points percentage with odd games
excluded, goal differential, and goals scored. Scheduled final GP is equal.
Completely unresolved ties use a seeded lottery, never alphabetical order.
The top three in each division qualify, plus the best two remaining clubs in
each conference. The better division winner faces the lower wild card. Each
division's two winners meet, without reseeding, then conference winners meet.
Series are best-of-seven, played in a 2-2-1-1-1 home pattern. Later-round home ice
uses regular-season record. Once the regular season ends, the official bracket
and confirmed series win counts must reconcile with computed seeding; actual
postseason wins are fixed and never resimulated.

Per-game random streams use official game IDs; rates and postseason streams
use the season. Identical inputs produce identical outputs. The live feed uses
50,000 seasons, with stage totals conserving exactly 16, 8, 4, 2 and 1 clubs.
Point distributions sum to 100% and first-round matchup probabilities sum to
each team's qualification probability. All main stage probabilities are
unconditional from the forecast time. Opponent cards explicitly condition on
qualification. Percentages can be converted to fair American/decimal odds;
they are not sportsbook prices. Simulation zero/one values are displayed as
<0.1% / >99.9%, not as mathematical clinching or elimination.

## Evaluation and limitations

`parameters.json` records parameter selection on 2024–25, an untouched 2025–26
walk-forward game evaluation, a fixed-home-rate baseline, reliability bins,
and retrospective playoff forecasts at three dates. At each game prediction,
only earlier games and earlier seasons enter team rates. Parameters are never
selected against the holdout season. Regenerate explicitly with:

```sh
python -B tools/playoffs/validate_history.py --playoffs
```

The first holdout performs close to the simple baseline. The UI identifies
this model as beta and publishes the result rather than claiming strong
predictive accuracy. Game-probability metrics do not establish calibration of
season/playoff probabilities; three snapshots from one season are diagnostic,
not sufficient calibration evidence. The retrospective snapshots use the
eventual official schedule; historical postponement announcement times are not
available. Current historical data is not used to invent past published odds.

Goal totals include empty-net and awarded shootout goals. V1 does not model
injuries, lineups, starting goalies, expected goals, trades, or future roster
changes. More simulations reduce sampling noise, not model error. Cup estimates
are especially dependent on those strength assumptions. A future stronger
model should be versioned and evaluated on new untouched seasons.

Official rules:

- https://www.nhl.com/info/standings-info/playoff-format
- https://www.nhl.com/info/standings-info/tie-breaking-procedure

## League dashboard and game analytics

The default entry is the league-wide table, including after a team has been
saved locally. Team cards are shown only in the optional Team detail tab or
when opening a frozen share. The board defaults to fair American odds with
percentages alongside them, with decimal and percentage options. Season stats
expose official records, win/points percentages, GF/GA, RW/ROW, and last-ten form.
CSV downloads contain numeric percentages and both fair-odds formats.

Circle view is an independent SVG chart with five nested rings (playoffs to
champion) and a single-round option. Slices divide each round's expected places
among teams; a qualification ring is normalized over 16 places, not over 100%
of independent qualification probabilities. The labels/readout show the actual
team probabilities. The Cup ring sums to one champion. Team colors are stable
across rings. Hover, focus, and touch inspection retain the optional team view.
Team crests sit directly inside the outer colored slices, sized to stay within
their geometry. Tiny slices keep their original angles without forcing in a
logo; all 32 crests remain available in the legend. Transparent image padding
is trimmed using the existing local-crest loader, with updates applied to the
image nodes without rebuilding the chart or intercepting pointer interactions.

`games.py` adds the last 14 days and next seven days of games. Before-game win
probabilities use the model's posterior mean scoring rates; the season model
also samples team-strength uncertainty. Upcoming numbers can update before
the start. Once play begins, any estimate saved before that start is frozen.
For older results without a saved estimate, reconstruction uses only completed
games from strictly earlier calendar dates, excluding same-day overlapping
games. Reconstructed values are labeled throughout and are not represented as
previously published forecasts, sportsbook prices, or in-game estimates.

Final scores and shots are reconciled against NHL boxscores. Missing shots
stay missing rather than becoming zeros. Recent boxscores are rechecked for
corrections; older verified shots can be reused from the preceding feed. The
goal awarded for a shootout win is excluded from goals-per-shot calculations.
Scoring estimates are not presented as shot-based expected goals or a
deserve-to-win metric. No sportsbook feed was added.
