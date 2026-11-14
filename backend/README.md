# Sweater API and private analytics

This project targets the existing `sweater-api` Worker and its `DB` binding to
`sweater-leaderboard`. `src/existing-api.mjs` retains the supplied leaderboard
and Party Mode implementation. `src/index.mjs` routes analytics, Grid popularity and live hockey paths to
their respective handlers; other requests retain their existing behavior.

## Live game percentages

`GET /api/playoffs/live?date=YYYY-MM-DD` reads the official NHL score/clock and
the saved Sweater pregame forecast directly from the existing Worker. It needs
no new credentials or database. Score responses and calculated estimates are
cached at the edge for 30 seconds, and the forecast input for 60 seconds.
Only yesterday, today and tomorrow in NHL's Eastern calendar are accepted.
The Games view polls while visible and stops on navigation or a hidden tab.
Live refreshes update score/probability cells without closing team availability.

The live model conditions independent Poisson scoring on the current score and
regulation time remaining, using saved expected-goal rates. Its prior is matched
to the saved pregame win probability. Regular-season overtime survival uses
869 OT games / 278 shootouts from official 2023–24 through 2025–26 NHL schedules;
playoff overtime has no shootout. These aggregate schedules are already cached
by `tools/playoffs/data.py`. This first live model is not yet backtested against
historical in-game states. Current penalties, empty-net play and mid-game goalie
changes are not separately modeled. Shootouts show unavailable until final;
missing or stale feeds never become fresh-looking pregame percentages.

The original pregame forecast is retained for Results and forward evaluation.
This endpoint does not change standings or the season/playoff simulations.

## Playoff refresh clock

The GitHub workflow targets a fifteen-minute schedule, but scheduled Actions have
been observed to arrive much later. The existing Worker therefore has a separate
minute cron that can dispatch the same validated Python workflow when the public
forecast is over fifteen minutes old. Daily analytics/popularity cleanup remains on
its original daily cron. The watchdog avoids queued/running jobs and limits
retries to one dispatch per five minutes. It never publishes unvalidated data.

One credential is needed to activate this clock:

1. Create a fine-grained GitHub personal access token for **only
   `cartsybends/sweater.win`**, with repository **Actions: Read and write**.
   No Contents write permission is needed. Set an expiration and renew it before
   it expires.
2. In Cloudflare, open **Workers & Pages → sweater-api → Settings → Variables
   and Secrets**. Add **`GITHUB_REFRESH_TOKEN`** as an encrypted secret and deploy
   the settings change. Do not paste it into chat, a file or a public variable.
3. The minute watchdog then calls the existing `refresh-playoffs.yml` workflow
   through GitHub's authenticated dispatch API. A source outage can still delay
   publication; the site always shows the real last successful check. Cron
   configuration changes can take several minutes to propagate at Cloudflare.

Without that secret the watchdog is inactive and makes no network requests;
GitHub's original schedule remains the fallback. The X token is unrelated, and
RSS mode needs no paid X access. There is no public dispatch endpoint.

In Observability logs, filter for **Playoff refresh watchdog**. A successful
dispatch has status `dispatched`. Failures include an HTTP status or an
allowlisted exception type and a static `stage`, such as `github_runs_fetch`
or `github_dispatch`. No tokens, headers, response bodies or raw exception
messages are logged. Authenticated requests use manual redirect handling so
the token cannot be forwarded to another destination. A workerd runtime test
checks these requests in addition to the mocked workflow tests.

## Connect the existing Worker to GitHub

After the source is saved in `cartsybends/sweater.win`:

1. In Cloudflare, open **Workers & Pages → sweater-api → Settings → Builds → Connect**.
2. Authorize the Cloudflare GitHub app for `cartsybends/sweater.win`.
3. Set production branch to `main`, root directory to `backend`, build command
   to `npm run build`, and deploy command to `npm run deploy`.
4. If a preview command is requested, use
   `npx wrangler versions upload --config wrangler.generated.json`.
5. Save the connection. A push to `main` starts the production build.

The build command prepares `wrangler.generated.json` with the existing D1 database.
Both deploy commands must use that generated configuration.

The configuration helper resolves the existing database by name with Wrangler.
It fails if the database cannot be found uniquely, and never creates a database.
If the build token cannot list D1 databases, copy the existing database's Database
ID into the **build variable** `SWEATER_D1_DATABASE_ID`. The ID is a resource
identifier, not a password. The token needs permission to deploy this Worker and
use this existing D1 binding.

`keep_vars: true` retains dashboard-managed `ALLOWED_ORIGINS` and `SCHEDULE_URL`.
Cloudflare secrets remain in Cloudflare. The custom domain stays `api.sweater.win`.
The tracked configuration contains no account credentials or database IDs.
Its zero UUID is a dry-run placeholder. The deployment command resolves the real
existing database and refuses to deploy that placeholder.

Who Scored? uses the existing leaderboard and result tables: daily wins earn
10, 8, 6, 4, 2 or 1 point by guess count, and losses earn 0. The Worker checks
the published `whoscored_days` assignment and keeps the first result per player
and day. Today, Week and All time use the same rankings as the other games.
Deploy the Worker together with the frontend update to enable this board.

Deep Cut uses the same result tables and daily rankings. The Worker replays
exactly seven player IDs or `MISS` actions against the published `deepcut_days`
assignment and frozen `deepcut` answer bank in `schedule.json`. Points are
calculated from that bank, never a client-provided score; the maximum is 700.
Deploy the Worker alongside the frontend to enable the new leaderboard. Until
then, local saves, XP, practice, and sharing work normally; unknown-game
submissions remain eligible for retry after the API rollout.

## Activate private analytics

In **sweater-api → Settings → Variables and Secrets**, add a **Secret** named
`SWEATER_ANALYTICS_PASSWORD`. Use a password-manager-generated password with at
least 32 characters, keep it private, and save/deploy the change.

Then visit **https://api.sweater.win/analytics** and sign in with that password.
Login cookies are signed, expire after 6 hours, and are Secure, HttpOnly, and
SameSite=Strict. Every report request is authenticated on the server. Reports
and private pages use `no-store`, and the password is never sent to the public
frontend or stored in this repository.

Collection stays disabled until the Worker has its DB binding and private
password configured. The public site checks availability before sending events;
an unavailable backend does not affect gameplay. It honors Do Not Track and
Global Privacy Control when those browser preferences are enabled.

## What is measured

- Home visits, page loads, game opens, and navigation between modes.
- Daily, Unlimited, Archive, Party, and the four independent Teams mini-games.
- Anonymous recognized browsers, visits, and browser-tab sessions. All random
  browser, visit, session, and round IDs are keyed hashes in the database.
- New, returning, and repeat visitors; next-day and day-seven return cohorts.
- Round starts and finishes, started-round finish rate, supported win rates,
  actions/attempts, scores, foreground response and completion times, answer
  accuracy where supported, and first exits from unfinished rounds.
- Foreground active time, paused when hidden/unfocused or idle for 45 seconds.
- Shares recorded after successful result copies, favourites, library filters,
  stats/help/profile/archive opens, challenge copies, team choices, and Party joins.
- Coarse device, browser, operating system, country, theme, and viewport categories.
- Search/social/direct/referral source categories, plus safe `utm_source`,
  `utm_medium`, and `utm_campaign` labels. The Traffic section builds tagged links.
- Browser-provided load, first-byte, largest-paint, and layout-shift samples; up to
  ten anonymous JavaScript/promise/resource diagnostics per visit. New reports
  include a frontend release fingerprint, allowlisted error types, locations in
  Sweater's own scripts, failed-asset categories and browser online/offline state.
  Only Who Scored's public, neutral media filenames are retained; headshot player
  IDs, arbitrary filenames, full URLs, query strings, error messages and stacks
  are excluded. The release fingerprint changes with frontend code or clip assets.
- Today, 7/30/90/365-day and custom-date reports, previous-period comparisons,
  daily charts, weekday/hour heatmaps, filters, CSV exports, and full report JSON.

Visits are tracked page loads, sessions are browser tabs, and visitors are
recognized anonymous browsers rather than identifiable people. Blocked or cleared
storage can create a new visitor. Devices and browsers can obscure their category.
Recent activity means signals received in the last two minutes, not an exact
online headcount. Country is derived from Cloudflare's country field, not saved IPs.

Sweater Grid's answer-popularity feature uses separate `/api/grid/answers` and
`/api/grid/popularity` endpoints. Only valid, correctly filled squares from
finished Daily or Unlimited runs contribute; revealed example solutions and
Archive replays do not. It stores public NHL player IDs and canonical clues,
with one keyed anonymous-browser vote per clue intersection, and removes votes
after 365 days. Opt-out, Do Not Track, and Global Privacy Control apply. The
public endpoint contains aggregate counts only, without browser identities.
At least 100 answers are required before rarity changes bonuses, and daily
puzzles and saved unlimited runs freeze their scoring snapshots.

The Browser errors table groups the same issue by release and code location or
asset, and lists affected sessions first. Start with recurring reports in the
current release. Resource failures can come from a missing file, a failed decode,
the visitor's connection or a blocker; a category alone does not establish a
cause. Old category-only rows retain their counts but cannot gain missing details.

Deploy the backend changes through the existing Cloudflare Worker connection to
activate diagnostics. `/api/analytics/status` advertises `diagnostics: 1` when
supported. Until then, the upgraded client continues sending the original event
fields. The backend creates a separate diagnostic table without altering existing
analytics tables, and expires diagnostic rows with their original events.

Finish rate follows rounds started in the selected period and completed by that
period's end. Finishes can include rounds started earlier. First unfinished exits
can later be completed; simply reading or pausing a round is not counted as an
abandonment. Party, Best Lineup, and endless Teams Higher/Lower completions have
no binary win outcome. Scores and action counts are compared within each game.
The Teams landing page has no rounds. Return cohorts wait for their day-one or
day-seven windows and count later activity anywhere on Sweater, even if its
source changes. Unsupported performance measurements are blank, never zero.

The payload excludes names, emails, typed guesses, target/scorer IDs, leaderboard
credentials, room codes, full URLs, raw referrers/user agents, and error messages
or stacks. No keystrokes, recordings, or precise location are collected. The
dashboard exposes aggregates only and requires the existing owner sign-in.

Use **Exclude my visits on this browser** in the dashboard to open
`https://sweater.win/?analytics=off`, which saves an opt-out on that browser.
`?analytics=on` includes it again. Each device/browser has its own preference;
Do Not Track and Global Privacy Control still take precedence.

The Worker creates separate `sweater_analytics_*` tables automatically.
Existing leaderboard, Party, and original analytics event tables are preserved.
Version 2 adds detail, visitor, session, and metadata tables; no manual migration
or new database is needed. Batches contain at most five events, are validated
before writes, and stay within D1 statement and parameter budgets. Older clients
continue sending their original event format until they reload. Retries and
round replays/restoration retain separate deduplication rules.

A daily maintenance trigger prunes events older than **365 days** in bounded
batches; ingestion also prunes stale rows. Only temporary hashed IP buckets are
used for request/login rate limits. Visitor first-seen dates remain available
while that browser continues returning, to distinguish new and returning usage.

Existing basic game totals remain visible. Detailed visitors, progression,
sources, and performance begin when visitors load the expanded client; unavailable
historical details cannot be reconstructed. The dashboard shows coverage when
a selected range includes sessions without those details. Reports use Vancouver
calendar dates and hours.

## Local verification

```sh
node tests/analytics_backend.mjs
node tests/analytics_login.mjs
node tests/analytics_client.mjs
node tests/analytics_client_v2.mjs
node tests/analytics_insights.mjs
node tests/analytics_dashboard.mjs
node tests/who_scored.cjs
node tests/who_scored_leaderboard.mjs
node tests/shootout.cjs
SWEATER_D1_DATABASE_ID=00000000-0000-0000-0000-000000000000 npm --prefix backend run build
```

The zero UUID is only for local packaging/CI dry runs. Production uses the existing
database resolved from Cloudflare or the actual build variable.

The richer report and dashboard checks use real in-memory SQLite aggregates and
a DOM simulation. Frontend tests exercise legacy fallback and enhanced batching,
privacy preferences, attribution, round restoration, timing, and network retries.
