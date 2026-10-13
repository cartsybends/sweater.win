# Sweater API and private analytics

This project targets the existing `sweater-api` Worker and its `DB` binding to
`sweater-leaderboard`. `src/existing-api.mjs` retains the supplied leaderboard
and Party Mode implementation. `src/index.mjs` routes only analytics paths to
the new handler; other requests retain their existing behavior.

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
  ten anonymous JavaScript/promise/resource error categories per visit and build.
- Today, 7/30/90/365-day and custom-date reports, previous-period comparisons,
  daily charts, weekday/hour heatmaps, filters, CSV exports, and full report JSON.

Visits are tracked page loads, sessions are browser tabs, and visitors are
recognized anonymous browsers rather than identifiable people. Blocked or cleared
storage can create a new visitor. Devices and browsers can obscure their category.
Recent activity means signals received in the last two minutes, not an exact
online headcount. Country is derived from Cloudflare's country field, not saved IPs.

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
node tests/shootout.cjs
SWEATER_D1_DATABASE_ID=00000000-0000-0000-0000-000000000000 npm --prefix backend run build
```

The zero UUID is only for local packaging/CI dry runs. Production uses the existing
database resolved from Cloudflare or the actual build variable.

The richer report and dashboard checks use real in-memory SQLite aggregates and
a DOM simulation. Frontend tests exercise legacy fallback and enhanced batching,
privacy preferences, attribution, round restoration, timing, and network retries.
