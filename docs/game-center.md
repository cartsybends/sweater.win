# Live Game Center

The Games entry **Team availability / Game Center** opens a large view, with
Game Center, Lines & units, Matchups and Availability tabs. There is no extra
navigation section.

## Live data and serving

`GET /api/playoffs/game?id=<NHL game ID>` only serves games in the published
`playoffs_cache.json` window. It checks game ID, teams and puck-drop time against
that schedule before transforming official NHL `/gamecenter/<id>/play-by-play`.
It never calls MoneyPuck's live prediction endpoints.

The existing Cloudflare Worker runs the small JS inference and caches a compact
response for 15 seconds live, 60 seconds scheduled/final. The Cache API is local
to each Cloudflare data center, not one global fetch lock. Concurrent requests
inside an isolate coalesce. A one-day last-good cache can survive source errors;
its original timestamp stays intact and the response explicitly says `stale`.
Without a valid fallback the endpoint returns 503.

The browser polls only the open, visible view, aborts on close/navigation/hide,
retains filters and selection, and marks failed checks as delayed. Checks target
15 seconds, not instantaneous delivery: NHL publication, cache and network delays
remain. No GitHub Actions refresh or AWS service is involved in this live path.
Saved pregame forecasts and the broader season simulation retain their existing
refresh pipeline. The market panel reuses the separate existing live quote feed.

## Win curve

The curve reconstructs score/clock states from the current official event log
against a frozen **recorded/pregame** forecast. It calls the same conditional
Poisson model as the Games table, preserving the prior at 0:00 and showing both
complementary team probabilities. Goals include before/after samples at the same
time. Final results resolve to 100/0. Shootout award goals are excluded from
regulation-event reconciliation; no current probability is shown during an
ongoing shootout. Missing frozen forecasts, missing clocks, or score/event-log
mismatches suppress the curve rather than fabricate history. Official NHL
corrections can revise earlier points.

The beta win model now conditions on supported timed penalties using the same
calculation in Game Center and the Games feed. Pulled goalies, individual skater
matchups, in-game shot quality and individual shootout attempts remain outside
this adjustment. Shot-quality percentages do not independently change the curve.
The readout uses period and time remaining. Event icons sit at their corresponding
team's curve point, with short leaders when needed to avoid covering another
marker. Five-minute clock ticks restart within each period.

## Sweater shot model

`tools/playoffs/train_shots.py` fits logistic regression to factual events and
actual goal outcomes from publicly listed MoneyPuck shot downloads, with clear
MoneyPuck.com credit. No MoneyPuck predicted xGoal/probability field is a feature
or target. Keep raw archives outside Git. This usage remains noncommercial.

- Fit: 2023–24 and 2024–25.
- Calibration: 2025–26 logistic calibration.
- Holdout: 2026–27 snapshot, 26,025 eligible attempts; 25,818 goalie-in-net.
- Goalie-in-net holdout: Brier 0.063718, log loss 0.235385, AUC 0.73501.
- Inputs: distance, angle, their transforms/interactions, shot type, rebound,
  skater counts, empty-net indicator (the released domain excludes empty nets).
- Export: `backend/src/shot-model.mjs`, coefficients plus exact input SHA-256s,
  validation bins, feature order and source URLs. No runtime NumPy dependency.

The training coordinate convention does not adequately represent own-half shots.
The released percentages therefore apply only to located, unblocked attempts in
the offensive half, with a goalie in net and valid strength context. Empty nets,
own-half, blocked, unlocated, unsupported-context and shootout attempts receive
no percentage. Shot-quality totals explicitly cover supported attempts only.
There is no individual shooter or goalie adjustment. Validation is a snapshot,
not evidence of future superiority to MoneyPuck or sportsbooks.

Run training offline with NumPy installed:

```sh
OPENBLAS_NUM_THREADS=2 python -B tools/playoffs/train_shots.py --data /path/to/archives
```

The directory must contain `shots_2023.zip` through `shots_2026.zip`, downloaded
from the explicit links on https://moneypuck.com/data.htm. Training writes an
additional validation report beside the archives. Release gates compare held-out
Brier/log loss against an average-shot baseline and check calibration and sample
size. Revisiting model choices after evaluation requires a new independent test
period before claiming an untouched holdout.

## Rink and accessibility

NHL defending-side information rotates coordinates per period. The display then
keeps away attacking left and home attacking right. The rink uses 200×85-foot
geometry, a goal line at 89 feet, blue lines at ±25 and regulation faceoff circles.
Blocked locations represent the block, not an inferred release point. Missing
locations remain in the event list. Shot filters and a keyboard-accessible event
list offer an alternative to crowded dots. A compact graph readout follows the
hovered/pressed point, showing both teams, clock, score and the relevant event.
Its position stays inside the chart on phones; leaving the plot, scrolling or
pressing elsewhere dismisses it. The legend retains the latest probabilities.
Chart arrows/Home/End explore history with the same readout and a screen-reader
announcement. Escape first dismisses an open readout, then closes the dialog.
Shot details remain below the rink. Goal rows have an explicit scoring label,
scorer, assists and resulting score; details separate primary/secondary assists
from shot measurements. Empty-net goals show the empty net rather than a large
missing-chance placeholder. Close restores focus and native Dialog maintains
background focus containment.

Verification: `node tests/playoffs_gamecenter.mjs` and, after installing backend
packages, `node tests/playoffs_gamecenter_runtime.mjs` exercise the real workerd
Cache API as well as model/event, identity, outage and client contracts.

## Events, team colours and mobile rink zoom

Goal cards include the NHL goal score and primary/secondary assists in source
order. “None listed” reflects an empty current NHL assist list; later official
corrections replace those details. Penalty records include reason, duration,
committing player, drawn-by player and served-by player when present. Bench
penalties do not invent a committing player. Alarm and striped referee markers
are placed on the probability plot. Dense nearby events share a counted marker with
all events retained in its details. Details stay inline on mobile.

The graph uses the same team-colour palette as the playoff circle. RGB distance
below 100 adds a dashed away line; otherwise both lines are solid. Both logos,
labels and swatches remain visible. The moneyline panel independently labels
each price with its team logo and abbreviation. Percentage axes include 0, 25,
50, 75 and 100. Shaded periods, labelled headers and separated end labels prevent
End P3 / OT collisions on narrow screens. Overtime uses five-minute regular
season periods or twenty-minute playoff periods.

Shootouts have a separate simple feed, ordered by official NHL sort order.
Rounds are each team's count of published attempts, so either team may shoot
first. Sudden death is labelled from Round 4. A shot-on-goal is a save credited
to the listed goalie; a missed shot does not get save credit. NHL
`failed-shot-attempt` is “Unsuccessful,” with no invented miss or save cause.
Shootout attempts never enter normal goals, shot xG or rink shot filters. No
in-progress shootout win probability is fabricated.

Rink controls offer fit, 2× and 3× zoom. A zoomed viewport uses native horizontal
and vertical panning, and reset returns to fit. Selection uses the enlarged
rink's actual geometry. Zoom and pan survive feed redraws; changing games resets
to fit. The event list remains an alternative to tapping crowded markers.

## Penalty-aware live model

`penalty-state.mjs` reconstructs assessed penalties from official play order and
playing time. Supported minors/bench minors expire after two minutes or a
power-play goal; double-minors have two serial two-minute legs; majors and match
penalties continue after goals. Coincidental calls, serial penalties to one player,
queued third penalties, misconducts, penalty shots, regular-season OT and Rule
19.4 differentials are handled separately. An extra attacker never invents a
power play. The tracker checks official on-ice counts; inconsistent, unsupported
or stale play-by-play receives an explicit score/clock fallback. A source returning
to verified even strength can resolve that uncertainty.

`fit_penalties.py` uses official NHL `goalsforbystrength` and `powerplaytime`
reports for the completed 2023–24 and 2024–25 seasons. Six strength scoring rates
(5v4/4v5, 5v3/3v5, 4v3/3v4) use a Jeffreys half-goal prior. Report definitions
separate empty-net/extra-attacker goals from skater-strength goals; PP clock
exposure does not perfectly isolate goalie-in-net time. These are average
strength rates, not an individual shooter, goalie or special-teams-unit model.

The later 2025–26 goal-rate check has Poisson deviance 8.86, versus 1546.12 for
an all-strength average-rate baseline. This evaluates strength **scoring rates**
and is not full live win-probability calibration. Input URLs and SHA-256 hashes
are embedded in `penalty-rates.mjs`; raw responses remain outside Git. Regenerate
with `python -B tools/playoffs/fit_penalties.py --data /path/to/private/cache`.

The live projection scales those rates by saved pregame scoring strength and
known remaining penalty clocks. Single minors and double-minors account
analytically for early goal termination. Complex known penalty combinations use
five-second state occupancy steps, including minor releases and queued/serial
clocks. Mean remaining goals enter the existing conditional Poisson calculation;
this retains an independent-goals approximation and does not model future
unobserved penalties. OT integrates competing first-goal hazards and retains
known third-period penalty carryover. The saved pregame prior stays fixed.

An 80-game current-season spot check covered 291,635 playing seconds; 110 seconds
used the explicit manpower mismatch fallback. This is **decoder coverage**, not
probability accuracy. At 4,800 minute-spaced states, Brier was 0.173893 versus
0.174187 for score/clock; at 810 penalty-active states, 0.180925 versus 0.182591.
Game-cluster bootstrap intervals for the differences include zero. Some priors
were reconstructed, and official corrected logs are retrospective. These checks
do not establish a statistically reliable accuracy improvement or superiority
to MoneyPuck/sportsbooks. No coefficients were retuned on this spot check.

The Games feed and Game Center share the same NHL PBP edge cache and inference.
A newer scoreboard is never combined with stale penalty context. The live list
keeps its thirty-second polling cadence; an open Game Center targets fifteen
seconds. Missing market quotes and penalty sources remain independent.

Market attribution is centred beneath prices, with its timestamp directly under
the source and no “Observed” prefix. Its status still distinguishes a live,
suspended, last-known or saved pregame quote. Source links remain text-sized.

New website clients request `penalties=1` on `/api/playoffs/live`; the default
protocol stays on the existing score/clock calculation for already-open older
clients. The cache and request-coalescing keys separate those variants. Both
new views use `sweater-live-v2` when penalty context is available and explicitly
label a `sweater-live-v1` fallback. Goal-log totals must also reconcile before
applying a power play, preventing a delayed goal event from extending a released
minor after the score has already changed.

## Lineups, player outlook and head-to-head history

`GET /api/playoffs/preview?id=<NHL game ID>` serves a separately precomputed
report from `playoffs_lines/matchups/`. It uses the same published game-window
identity gate, checks both source and target game identities, and validates the
response with `static/playoffs/preview-model.mjs` on the server and client.
Reports cache for two minutes at the edge; a one-day last-good fallback keeps
its original timestamps and explicitly marks `stale`. The browser requests this
report only while Lines or Matchups is visible, polls every two minutes, and
aborts on hide, close, navigation or a switch to another panel. The live game
feed remains independent and retains its fifteen-second target.

`Refresh NHL Game Center previews` follows each successful season-forecast
refresh and also runs when its source/model changes. It downloads official NHL
stats and schedules with bounded concurrency and persistent source caches. It
publishes compact validated reports without embedding them in the main HTML or
running a large historical-data fan-out in Cloudflare. Refresh frequency follows
the existing season-forecast pipeline; the browser's two-minute check does not
mean a fresh full history is generated every two minutes. Current selected-game
scores and final results also update from the independent live game feed.

The lineup source is each team's last completed regular-season game strictly
before the selected game. Official boxscores identify dressed skaters and their
positions; official shift overlap identifies forward trios and defense pairs.
A maximum-weight disjoint set search ranks the most-used complete groups by
shared five-on-five time. It does not fill missing lines from roster order.
Eleven-forward/seven-defense games can therefore have an unidentified fourth
trio and a separate list of rotating players. PP/PK units come from unequal
skater counts while both goalies are present, excluding extra-attacker play.
No observed distinct second unit means no invented second unit. Arrows compare
observed usage rank with the previous game's combinations, not a confirmed
coaching promotion or demotion. Headshots use official NHL player IDs.

Season AVG SOG and AVG BLK are totals divided by appearances. Center faceoffs
use total wins/attempts; PP% and PK% use total team opportunities, not averages
of game percentages. Unknown values remain missing. All displayed averages and
model features use games with NHL `gameDate` strictly earlier than the target
NHL date, including September games in the 84-game 2026–27 season. UTC dates
are not substituted for the NHL schedule date.

`sweater-player-shares-v1` allocates the saved Sweater team goal forecast among
last-game dressed skaters. Its features use multi-season goal and shot rates,
recent/multi-season time on ice and PP role, a smoothed recent scoring change,
and strongly regressed history against the actual opponent franchise. A line's
expected goals are the sum of goals predicted to be scored by its players,
including special teams. This is **not on-ice shot-quality xG**, a chemistry
estimate or an independent team goal forecast. Forward/defense/other-player
allocations conserve the team mean; overlapping PP/PK groups are not additional
goals. Injuries already identified in team availability withhold the affected
complete group's forecast. Estimates otherwise remain conditional on those
players dressing and are labelled beta; upcoming coaching assignments are not
claimed to be confirmed.

`fit_players.py` warms up on 2023–24, selects regularization chronologically
within 2024–25, evaluates on 2025–26, then refits release coefficients through
2025–26. A later current-season snapshot is separate. Conditional goal-share
log loss was 2.669660 vs 2.680349 for the goal-rate-times-ice-time baseline over
2,624 team-games/8,086 goals in 2025–26. Through Nov 15, 2026 it was 2.670780 vs
2.677224 over 660 team-games/2,064 goals. This retrospective evaluation knows
who dressed, but no same-game performance feature is used. These figures do
not establish calibration of team/line totals or superiority to other sites.
Input row counts, hashes, coefficients and limitations are versioned in
`player_parameters.json`; raw historical rows stay outside Git. Refit with
`python -B tools/playoffs/fit_players.py`; generation uses NumPy but no SciPy.

A saved pregame report freezes its lineup and projection after puck drop;
matchup history can still refresh. Games without a saved report show a clearly
labelled reconstructed pregame estimate based on earlier games. They do not
claim to have been published before the game.

Matchups separates the selected season's complete scheduled series (past final
scores and future local dates/times) from the ten most recent completed meetings
as of the history check. Both include regular season and playoffs and exclude
preseason. NHL club schedules are reconciled by game ID and final result. Exact
franchise identities are retained; Arizona results are not relabelled as Utah.
A newer franchise can have fewer than ten meetings. Historical matchup results
are current context, separate from the strictly pregame model feature cutoff.

Goals in both the graph event card and rink detail show complementary win
chances from the `kind: goal` sample with that exact NHL event ID. They never
reuse the current/final win chance for an earlier goal, and the readout is
omitted when verified probability history is unavailable. The rink additionally
includes neutral-zone dots, end-zone inner L marks and outer hashmarks, and both
goaltender trapezoids using regulation 200×85-foot geometry.

Verification: `python -B tests/playoffs_previews.py`,
`node tests/playoffs_previews.mjs`, and (with backend packages installed)
`node tests/playoffs_previews_runtime.mjs`. Browser checks cover Chrome desktop,
iPhone WebKit and 320px touch layouts, all four tabs, keyboard navigation,
portrait retention, incomplete lines, goal-specific probabilities, local dates,
source outages and timer/request cleanup.

## Lineup readability and league special-teams ranks

Movement indicators use larger directional icons and high-contrast rank badges;
position/jersey labels and shared-ice-time values have larger, heavier text.
Portraits retain the full 336px NHL source with explicit intrinsic dimensions and
no transform/filter, displayed within a consistent responsive circle. Rink maps
place the designated home club's SVG crest beneath the center-ice markings.

PP% and PK% badges now include a league competition rank. Rates use exact season
goals/opportunities strictly before the selected NHL game date; ranks compare
unrounded fractions across all 32 clubs, with ties sharing a rank. Incomplete
league coverage or a zero-opportunity club suppresses the rank and medal rather
than claiming a leader. Top-three rates reuse the goalie gold/silver/bronze
palette and reduced-motion-aware sheen. Saved pregame reports may gain rank
metadata only when recomputed historical rates match their saved values; the
original lineup, scoring projections and timestamp stay frozen.
