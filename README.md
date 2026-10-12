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

## Supported permits

All of these were checked against the live API and appear in the dashboard's picker.

| Region | Permit | ID |
|---|---|---|
| Sierra Nevada | Mt. Whitney (day + overnight) | 445860 |
| Sierra Nevada | Inyo NF wilderness trailheads | 233262 |
| Sierra Nevada | Yosemite wilderness | 445859 |
| Sierra Nevada | Sequoia & Kings Canyon wilderness | 445857 |
| Sierra Nevada | Sierra NF wilderness | 445858 |
| Sierra Nevada | Hoover Wilderness (Humboldt-Toiyabe NF) | 445856 |
| Sierra Nevada | Half Dome day hike | 234652 |
| Southern California | PCT overnight, Cleveland NF | 445862 |
| Northern California | Lost Coast (King Range Wilderness) | 445864 |
| Pacific Northwest | Enchantments daily lottery | 445863 |
| Southwest | Paria Canyon overnight | 74984 |
| Southwest | Cedar Mesa backpacking | 445861 |

Itinerary-style national park permits (Glacier, Olympic, Grand Canyon backcountry and
similar) use a different booking app whose availability call I haven't found yet.

## Tests

```bash
python3 -m unittest discover -s tests
```
