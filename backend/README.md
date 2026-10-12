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

- Mode opens, separate from rounds started and finished.
- Daily, Unlimited, Archive, and Party usage.
- Browser-tab sessions, hashed by the server, not identifiable people.
- Foreground active time, capped by visibility/focus and a 45-second idle cutoff.
- Today, 7-day, 30-day and 90-day reports, trends, device categories and CSV exports.

The main game engine and Party Mode report rounds. The independent Teams
mini-games report navigation and active time; round columns show unavailable.
The collection payload excludes names, emails, guesses, target/scorer IDs,
leaderboard credentials, and referrers.

The Worker creates separate `sweater_analytics_*` tables automatically.
Existing leaderboard and Party tables are preserved. Event retries and round
replays/restoration have separate deduplication rules. A daily maintenance
trigger removes events older than 90 days; ingestion also prunes stale rows.
Only temporary hashed IP buckets are used for request/login rate limits.

No historical mode visits can be reconstructed from this new event collection.
Reports start when the backend is activated and visitors load the updated site.

## Local verification

```sh
node tests/analytics_backend.mjs
node tests/analytics_client.mjs
node tests/who_scored.cjs
SWEATER_D1_DATABASE_ID=00000000-0000-0000-0000-000000000000 npm --prefix backend run build
```

The zero UUID is only for local packaging/CI dry runs. Production uses the existing
database resolved from Cloudflare or the actual build variable.
