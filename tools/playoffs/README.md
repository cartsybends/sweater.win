# Playoff Picture

## Skater availability impact (beta)

`impact_parameters.json` is the offline-trained `sweater-skater-impact-v1`
release. It uses 3,851 verified regular-season games from 2023–24 through
2025–26, with 1,236 player records (unseen players receive a positional prior).
Official NHL shift membership is joined to factual MoneyPuck shot geometry,
shooter IDs and goal outcomes. Sweater's own shot model supplies shot quality;
MoneyPuck player rankings and predicted game probabilities are not targets.
Unmatched shifts, empty-net/unsupported strengths, incomplete goal logs and
games with less than 40 verified regulation minutes are excluded. Training
coverage and input hashes are published in the artifact. Arizona/Utah share
the existing historical rating identity; displayed head-to-head history still
uses the exact franchises.

The chance model is a ridge-regularized Poisson adjusted plus-minus fit with
separate even-strength, PP and PK offense/defense coefficients and club,
opponent, home and score-state controls. A shrunk goals-versus-own-xG finishing
component estimates shooting skill. Penalties and finishing shrinkage were
selected on 2024–25 after fitting 2023–24. A 2025–26 game-goal check selected
a 0.7 translation scale using skater coefficients fitted only through 2024–25.
The release then fits skaters through 2025–26; no current-season outcomes fit
the player, finishing or translation coefficients. Upstream 2025 shot-quality
calibration and game-strength training make that year's checks retrospective.

On 215 eligible 2026–27 games through November 13, game Brier was **0.2301**
versus **0.2311** without the adjustment; log loss was 0.6520 versus 0.6540.
The paired game-bootstrap 95% interval for Brier change is approximately
[-0.00200, +0.00010], including zero. This is a small conditional evaluation,
not proof of superior accuracy. Historical **dressed identities** are observed
retrospectively; all projected minutes use earlier games. Historical injury
report timestamps and their forecasting accuracy are not reconstructed. Game
checks do not establish playoff calibration. Only 12F/6D games with complete
sources enter this translation check; missing games are not filled with zeros.

Runtime projects role minutes from earlier NHL usage and prior seasons, budgets
replacement minutes across 12 forwards and six defensemen, and uses learned
low-usage positional priors for unknown players/call-ups. It compares projected
availability with the absence exposure already embedded in the base team's
recency-weighted ratings, avoiding a second full injury deduction. Injuries
marked Out/IR/suspended change scoring; DTD remains context until an out status
is reported. Effects can be small or positive; reputation never sets a minimum
star penalty. Coefficients are regularized associations, not causal guarantees.

Remaining-season draws use one recovery date per player per simulated season,
shared across games. Future reported estimates use a uniform ±7-day scenario
window, clipped after today; unknown returns use 7–28 days, and expired dates
use 1–14 days. These are explicit scenario assumptions, **not a medical return
model**. The eight highest-usage reported absences receive sampled returns;
additional absences stay excluded and are flagged partial. Postseason dates
advance approximately two days per game and two weeks per round. Future
unreported injuries/trades are not predicted. Stale/unavailable injury or usage
inputs disable individual adjustments rather than inventing availability.

Both game forecasts and season simulations consume the same artifact. Game
Center → Team availability and team breakdowns expose player estimates. Frozen
pregame predictions and archived dates retain their original version and values.
New pregame predictions also save the unadjusted win chance for an outcome-blind
paired comparison; `evaluation.py` separates the new impact version and its
shadow baseline from earlier forecasts. A fresh live game uses the saved,
adjusted pregame rates as its starting point; no historical fitting runs in
Cloudflare.

Training stays offline: install `requirements-training.txt`, cache official
NHL game/player reports with `data.py --history-only` and
`player_data.py --first 2023 --last 2026`, and provide the current compact NHL
schedule as `.cache/playoffs/lines/matchups-2026.json` (from `data.schedules`).
Download the factual `shots_2023.zip` through `shots_2026.zip` links explicitly
listed on MoneyPuck's data page into a private folder. Then run:

```sh
python -B tools/playoffs/impact_data.py --shots /path/to/private/shots
python -B tools/playoffs/fit_impact.py
python -B tools/playoffs/impact_artifact.py
python -B tools/playoffs/calibrate_impact.py
python -B tests/playoffs_impact.py
```

`calibrate_impact.py` also needs `advanced.load_inputs(2026)` cached inputs and
the existing fitted game-strength parameters. Raw downloads, shifts and sparse
design matrices stay outside Git. Only compact coefficients and diagnostics ship.
The normal forecast job fetches current usage with NumPy only and caches it;
SciPy is never required by the refresh job or Worker.

The public route is `/#playoffs`. The tool consumes `playoffs_cache.json`,
embedded at build time and fetched from the public main branch every two minutes
while visible. It preserves the last validated forecast on an error. Shared links
freeze the selected team's stats and probabilities at the original forecast time.
PNG sharing includes the Sweater S mark, URL, timestamp, and model-estimate label.

## Daily forecast archive

League, Circle and Team detail share a native calendar, previous/next saved-date
buttons and a Latest reset. A historical choice keeps all three views on the same
snapshot, including team records, all five stage probabilities, projected points,
distributions and opponents. Games and the existing intraday History view continue
to use the latest feed. Background checks update that live feed without replacing
the selected archive. CSV filenames include the archived date; shared team cards
retain the original forecast timestamp and values.

`playoffs_archive/index.json` lists saved days with SHA-256 content hashes. Daily
files use the NHL calendar in **America/New_York**, labelled Eastern Time in the
UI. Each date retains its latest successful data check, including the original
forecast/model timestamp; today uses the live forecast. Missing days have an
explicit unavailable state. The browser checks both the content hash and forecast
identity/shape before replacing its view, and retains the displayed data on error.
Requests cancel when leaving Playoff Picture or choosing a different date.

The normal verified forecast job calls `archive.capture` and commits the archive
with the live feed. A new check only updates its own date; older checks cannot
overwrite a newer snapshot. Compact files exclude live game/news payloads and the
growing intraday history. Initial dates from November 12, 2026 onward were recovered
from actual `playoffs_cache.json` commits on main, retaining source commit IDs.
Earlier dates are not reconstructed using today's model or standings. Repeating
the optional recovery uses the same latest-check rule:

```sh
python -B tools/playoffs/archive.py --backfill-ref origin/main
python -B tests/playoffs_archive.py
node tests/playoffs_archive.mjs
```

## Refreshing

```sh
python -m pip install -r tools/playoffs/requirements.txt
python -B tools/playoffs/data.py
python -B tests/playoffs_data.py
python -B tests/playoffs_advanced.py
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

Unchanged model inputs update `checked_at`, preserving `updated_at`, probabilities,
and history. Changes to results, schedule, advanced input revision, availability,
goalie reports, date, parameters, or model
produce a new forecast. The atomic file replacement occurs after conservation
and range checks. Data-only commits use `[skip ci]` and don't rebuild the site or
redeploy the API Worker. No new service, paid data feed, secret, database, or
betting account is needed. Public market quotes and injuries come from ESPN;
listed advanced-stat downloads come from MoneyPuck.com, credited in the footer.

## Model v2 (current beta)

`sweater-xg-v2` uses the same trained goal-rate engine for Games, remaining
regular-season simulations and playoff series. Features include recency-weighted
goals and expected goals, five-on-five shot quality, power-play/penalty-kill rates,
home advantage, team rest and projected goalie quality. MoneyPuck's listed team
game files and goalie downloads are reconciled with official NHL results and
goalie starts. No MoneyPuck predictions are copied.

Previous-season team strength uses the last three seasons at 60/30/10 weights,
regressed 35% toward league averages. A fitted 30-game prior decays with a
15-game half-life as current games arrive. Current-season results therefore
replace historical expectations faster than v1's fixed 60-game prior. Missing
current xG is left missing, never entered as zero. Historic xG can be revised by
its publisher and is not an as-published archive.

The separate conditional goalie model uses rest, last result, recent full-game
share, three-year playing time, age, two-year GSAx/save percentage, home ice,
roster size and a standings-based game-importance proxy. The last feature is not
exact playoff-odds leverage. Unconfirmed starters remain a probability mixture.
Current NHL rosters and identified goalie injuries constrain eligibility. A
source-confirmed starter overrides the mixture for that game only; a newer
injury/report conflict remains unconfirmed. A likely report is labeled separately
from the model's probability. **Skater injuries are reported context only:** no
unvalidated equal penalty is applied to every absent player. Estimated injury
return dates and future goalie rotations remain uncertain.

Simulation rates use the trained coefficients and the same game-specific rest
and goalie adjustments. Playoff series assume equal two-day team rest and
available-roster goalie probabilities; unknown future assignments are not
presented as confirmed. Gamma strength uncertainty is an approximation, not a
separately calibrated posterior. Simulated results do not retrain ratings inside
a run. The standings, bracket and probability-conservation rules below remain
the same.

`parameters_v2.json` records chronological selection on 2024–25 and evaluation
on 1,312 games in 2025–26: Brier 0.24506 versus v1's 0.25066; log loss 0.68289
versus 0.69481. Upstream goalie training is cross-fitted using only earlier
seasons. The live coefficients are subsequently refitted through 2025–26.
Retrospectively rebuilt xG prevents calling this an untouched end-to-end holdout.
These results do not establish superiority to MoneyPuck, sportsbook markets or
calibration of season/playoff probabilities. `playoffs_predictions.json` captures
actual pregame forecasts for forward evaluation; reconstructions are excluded.

Offline coefficient regeneration requires SciPy in addition to runtime NumPy:

```sh
python -B tools/playoffs/fit_advanced.py --inputs /path/to/chronological-inputs.json
```

The input bundle uses `advanced.load_inputs`'s `teams`, `goalies` and `births`
schema, covering team seasons from 2019 and goalie appearances from 2021 through
the evaluation season. Merge the listed historical downloads by game/team or
game/player key; current-season compact caches alone do not cover training.

## Goalie reports and optional X access

The default `STARTER_REPORT_SOURCE=rss` automatically reads RotoWire's published
NHL RSS feed, which its RSS page offers for blogs and personal websites. It
retains only game/player IDs, certainty, timestamps and source links, not news
prose. The publisher currently advertises a ten-minute TTL, which is respected;
conditional requests reuse ETag/Last-Modified snapshots. Earlier facts remain
available after items roll out of the short feed or a request fails. Unknown
players, wrong opponents/dates and ambiguous starting language never confirm.
The feed is not exhaustive and can lag the original reporter. The UI shows its
last successful check. RSS mode never makes paid X requests. MoneyPuck homepage
starter scraping remains disabled while the owner awaits permission.

`starter_reports.json` contains manually reviewed, game-specific sourced facts.
`starter_sources.json` lists official team accounts and selected beat reporters;
it can be extended after checking a reporter's identity and team coverage.
Clear starting statements can confirm; morning-skate/expected/likely language,
conflicting reports, retractions and different game dates are treated separately.
Only report facts, source URLs and timestamps are retained, not full posts.
The parser is conservative but is not a guarantee that every report is captured.

The optional recent-search connector makes read-only requests. Select
`STARTER_REPORT_SOURCE=x` to use it instead of RSS. To enable it,
configure the GitHub Actions secret `X_BEARER_TOKEN` and the repository variable
`X_MAX_POSTS_PER_DAY` with an explicit positive read cap. The default is **zero**,
including when a token exists. Do not put credentials in code, public files or
chat. Configure billing controls in X's developer console as well: a post-read
cap is not a guaranteed dollar spending limit. The job polls no more often than
15 minutes and requests at most ten posts per query, respecting its remaining
daily allowance. Source cursors and read counts persist in the public feed;
credentials never do. No X writes or direct messages are used. Access/credit
failures leave statistical projections available without claiming confirmation.

## Model v1 (legacy baseline and shared simulation rules)

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
qualification. Percentages can be converted to fair American odds;
they are not sportsbook prices. Simulation zero/one values are displayed as
<0.1% / >99.9%, not as mathematical clinching or elimination.

## Legacy evaluation and shared limitations

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
when opening a frozen share. The board defaults to percentages with American
odds as the only alternate format. Season stats
expose official records, win/points percentages, GF/GA, RW/ROW, and last-ten form.
CSV downloads contain numeric percentages and fair American odds.

Circle view is an independent SVG chart with five nested rings (playoffs to
champion) and a single-round option. Slices divide each round's expected places
among teams; a qualification ring is normalized over 16 places, not over 100%
of independent qualification probabilities. The labels/readout show the actual
team probabilities. The Cup ring sums to one champion. Team colors are stable
across rings. Hover, focus, and touch inspection retain the optional team view.
All team crests sit outside the circle, connected to their actual slice by a
leader line. Crowded logos use a second radial lane, with a small angular shift
only when both lanes are occupied. Layout checks keep every crest and its hit
area separate, including dense clusters as future probabilities change.
Every playoff percentage appears inside the outer ring. Narrow slices use
compact, rotated labels, staggered radially when needed to avoid collisions.
All percentage labels are white with a subtle shadow over lighter team colors.
Later-round percentages appear when there is room; every segment exposes its exact
probability through a pointer/focus/touch tooltip and the complete team-stage
readout. Smaller labels along the top edge of each ring identify all five stages
without covering the percentages below them. An existing NHL Stanley Cup photo
occupies the larger center opening.
The stage labels also select single-round views. Probability geometry stays
normalized within each ring; presentation radii do not affect the forecast.

Playoff Picture uses larger table, legend, tooltip and supporting text, with a
larger desktop circle. Fit, 2× and 3× zoom keeps detailed chart text readable on
small screens without widening the page; the circle scrolls within its own
region. Tooltips stay inside the visible chart area. Only the hovered team's
slices darken slightly; all other slices and logos retain full brightness.
Transparent image padding is trimmed using the existing local-crest loader.
League and Games table crests use 54-pixel boxes on desktop and 42-pixel boxes
on mobile. The separate `team-crests` assets change only the original SVG's
viewBox, using source-hashed measured bounds in `crest-bounds.json`. Official
paths and colours remain intact, with no bitmap conversion. Circle logos use
these vector assets directly instead of the PNG cropping cache.

Pointer updates are coalesced once per animation frame. Tooltip contents and
the team readout change only when the team or stage changes; layout bounds and
tooltip dimensions are cached, and movement uses a CSS transform. Highlighting
touches only the old and new team's cached SVG nodes. The popup dismisses on
leaving a slice or logo, entering chart gaps, scrolling, or leaving the page;
pending hover frames are cancelled so it cannot reappear after exit. Keyboard
focus and touch taps still expose the same data. Accessible slice labels remain,
without a native SVG title tooltip duplicating the custom popup.

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
The Games table always shows Sweater model win percentages. Market moneylines
are separate, observed two-way sportsbook prices sourced via ESPN, with provider,
link and observation time. They never fall back to a converted model probability.
Matching requires both clubs, home/away and start time. Missing prices stay
unavailable; stale and saved pregame prices are labeled. These quotes need not
match every bookmaker or represent a live market consensus.

Game start times explicitly use the visitor's device timezone and locale, with
the timezone abbreviation displayed. The date picker and game grouping use
local calendar dates derived from the start timestamp, including midnight and
DST transitions. NHL calendar dates remain unchanged in the model inputs.

Games uses the League table's 54px team-logo boxes (42px on mobile), emphasized
team/goalie names, and linked checkmarked confirmations. Unconfirmed percentages
describe the chance of starting and use a red-to-yellow-to-green scale; a likely
report links through its percentage. Confirmed does not mean a guaranteed win.
The separate Team availability panel lists current reported injuries, status
and estimated return dates. Passed estimates remain marked as awaiting an update;
they are never represented as an actual return. Starter distributions are not
repeated in that panel. Bookmaker-source links have only their text's hit area.

Goalie GP, GS, SV% and GAA are official current-season regular-season totals,
fetched once per refresh from the NHL statistics API and joined by NHL player ID.
Failed fetches retain dated cached totals. A player absent from a validated complete
season response has zero appearances; missing sources do not invent zeros.
Saved pregame contexts freeze their statistics, and current totals are never
backfilled into historical reconstructions. Missing historical totals are shown
as unavailable. These display statistics do not change the fitted model inputs.

### Game Center player and matchup reports

`python -B tools/playoffs/lineups.py` publishes official last-game combinations,
conditional player-scoring forecasts and season/last-ten matchup history under
`playoffs_lines/`. Historical stats, full schedules and raw HTTP caches remain
in `.cache/playoffs/lines`; compact observed lineups are reusable versioned
inputs. Source details, validation results, projection meaning and refresh
behavior are documented in [Game Center](../../docs/game-center.md#lineups-player-outlook-and-head-to-head-history).

`player_parameters.json` is a fixed release artifact, not refitted by the normal
refresh workflow. Offline refitting uses `fit_players.py` with NumPy and SciPy;
production generation needs only the existing NumPy requirement. New model
choices require a new independent evaluation period before claiming an untouched
holdout. The workflow `refresh-previews.yml` follows successful league forecast
refreshes, validates both source chronology and client payloads, and publishes
only those reports; preview failures do not prevent the base forecast refreshing.

### If playoffs started today

The optional standings view uses the displayed forecast's NHL standing sequences,
not simulated qualification probabilities or projected final points. Each
conference takes the top three teams in each division plus its two remaining
wild cards. The stronger division winner faces WC2 and the other faces WC1,
including same-division wild cards. Division second/third seeds meet. Current
snapshots preserve NHL conference/division/wild-card sequence metadata;
previously saved archives retain their original official league sequence.
No advancing team is invented for later rounds of the radial bracket.

The league board keeps all 32 rows, disabling and dimming nonqualifiers only
while this view is selected; returning to forecasts restores every team.
Changing archive dates rebuilds the field from that snapshot. Official NHL
x/y/z/p clinch indicators highlight the team column independently of this mode.
A model probability of 100% never creates a clinch. The probability heatmap is
on by default, progressing from red through amber to green without changing
numbers or formatting. The additional one-line provider credit appears only in Playoff
Picture; the original player-data, creator and NHL attribution footer remains
on the homepage, Playoff Picture and other games.

`node tests/playoffs_field.mjs` checks the sixteen-team field, cross-division
wild-card rules, official rank priority, malformed metadata, independent clinch
indicators and radial-logo spacing. Existing model/live/archive validations
remain unchanged. Browser verification additionally covers field toggling,
disabled rows, pointer/keyboard/touch interactions, zoom, dated snapshots,
responsive readability and footer visibility on other routes.
