# permit-tracker

Watches recreation.gov wilderness permit quotas (Mt. Whitney, Inyo NF trailheads,
Sierra NF, and other permits) and pings your phone when a spot opens for the dates
and trailheads you care about. Python 3.9+, **no dependencies**.

See [API_NOTES.md](API_NOTES.md) for how recreation.gov's availability calls work.

## Quick start

```bash
# edit config.json: dates, trailheads, party size, ntfy topic
python3 -m permit_tracker divisions 233262 --grep bishop   # find trailhead IDs
python3 -m permit_tracker peek 445860 2027-07-01 2027-07-31 # eyeball availability
python3 -m permit_tracker check         # one pass
python3 -m permit_tracker watch         # poll forever, alert on new openings
```

## Alerts

- **Phone push (default):** install the free [ntfy](https://ntfy.sh) app, subscribe to
  a long random topic name, and put the same name in `notify.ntfy_topic`. No account.
- **Desktop:** macOS notification / Linux `notify-send` when `notify.desktop` is true.
- **Email:** set `notify.email_to` plus `SMTP_USER` / `SMTP_PASSWORD` env vars
  (Gmail: use an app password).

You get one alert when a date goes from below your party size to at or above it, not
on every poll. Every change is logged in `permit_state.sqlite3` (`history` table).

## Watch options

| key | meaning |
|---|---|
| `permit_id` | number from the recreation.gov URL (`/permits/445860`) |
| `divisions` | trailhead IDs from the `divisions` command |
| `division_names` | substring match on trailhead names, instead of IDs |
| `start` / `end` or `dates` | entry-date range, or an explicit list |
| `weekdays` | e.g. `["fri","sat"]` |
| `min_party` | alert only when at least this many spots are left |
| `api` | `auto` (default), `inyo`, or `permits` |

## Common permit IDs

| permit | id |
|---|---|
| Mt. Whitney (day + overnight) | 445860 |
| Inyo NF wilderness trailheads | 233262 |
| Sierra NF wilderness | 445858 |
| Half Dome (day use) | 234652 |

Yosemite (445859) and SEKI (445857) wilderness use a different API and aren't supported yet.

## Run it on GitHub Actions (no computer needed)

`.github/workflows/check-permits.yml` runs `check` every ~10 min on GitHub's servers.

1. Edit `config.json` (it's committed, so keep secrets out of it).
2. Add a repo secret **`NTFY_TOPIC`** (Settings → Secrets and variables → Actions)
   with your ntfy topic.
3. Actions tab → *check permits* → **Run workflow** once to test.

The alert state is carried between runs in the Actions cache. Caveats: GitHub's
cron can lag by several minutes at busy times, and recreation.gov may throttle
datacenter IPs more than a home connection. If runs start logging
`[rate-limited]`, run `watch` at home instead.

## Tests

```bash
python3 -m unittest discover -s tests
```
