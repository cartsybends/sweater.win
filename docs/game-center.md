# Live Game Center

The Games entry **Team availability / Game Center** opens a large view, with
Game Center and Team availability tabs. There is no extra navigation section.

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

This beta win model does **not** yet condition on in-game penalties, pulled
goalies, shot quality or shootout attempts. These limitations are disclosed in the
view. Shot-quality percentages do not independently change the win curve.

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
list offer an alternative to crowded dots. Both win values appear below the
chart on interaction; shot details sit below the rink instead of a large mobile
popup. Chart arrows/Home/End explore history. Close restores focus and native
Dialog handles Escape and background focus containment.

Verification: `node tests/playoffs_gamecenter.mjs` and, after installing backend
packages, `node tests/playoffs_gamecenter_runtime.mjs` exercise the real workerd
Cache API as well as model/event, identity, outage and client contracts.
