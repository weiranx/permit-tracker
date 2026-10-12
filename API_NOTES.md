# How recreation.gov loads permit availability

The permit pages are a React app. The calendar and trailhead grid aren't rendered on
the server; the browser calls unauthenticated JSON endpoints under
`https://www.recreation.gov/api/`. No API key, no login, and none of it is documented.
The official RIDB API (`ridb.recreation.gov`) has facility metadata but **no availability**.

## How this was verified

Endpoint paths came first from the source of open-source clients
([mdeckebach/recdotgov](https://github.com/mdeckebach/recdotgov),
[JamalMansuri/campsiterecon](https://github.com/JamalMansuri/campsiterecon),
[camply #22](https://github.com/juftin/camply/discussions/22)). Every shape below was
then **confirmed live on 2026-10-12** from a GitHub Actions runner, which is also where
three bugs in the first draft showed up (wrong Whitney ID, partial-month ranges,
unreleased dates looking open).

## 1. Permit metadata: `GET /api/permitcontent/{permit_id}`

```
payload.name
payload.divisions: { "<division_id>": { id, name, code, district, description,
                                         latitude, longitude, permit_id, version } }
```
A **division** is a trailhead / entry point / zone; it's the unit quotas are set on.

## 2. Inyo-style quota permits: `GET /api/permitinyo/{permit_id}/availabilityv2`

Params: `start_date=YYYY-MM-DD`, `end_date=YYYY-MM-DD`, `commercial_acct=false`.
**The range must be exactly one calendar month** (1st to last day). Anything else →
`400 {"error":"requested dates are invalid - can only be start/end of the month"}`.
A permit this endpoint doesn't serve → `400 {"error":"invalid permit id"}`.

```
payload: { "<YYYY-MM-DD>": { "<division_id>": {
    quota_usage_by_member_daily: { total, remaining },
    is_walkup, not_yet_released, release_date } } }
```
Confirmed for **Mt. Whitney (445860)**, Inyo NF wilderness (233262) and Sierra NF
(445858). The date is the **entry date**; `remaining` is people left on that
trailhead's quota. Things that look like availability but aren't:

| Signal | Meaning |
|---|---|
| `not_yet_released: true` + `release_date` | Not bookable yet (Inyo: 6-month rolling window, 7 am PT) |
| `is_walkup: true` | Inside the walk-up window; in-person only |
| `remaining` ≈ 899990 | Non-quota trailhead, no limit |
| Whitney `remaining == total` far out | Lottery dates not released yet; no flag is sent |
| Month beyond the window | `{"payload": {}}` |

Mt. Whitney's old ID **233260 is retired**: its generic endpoint returns empty data
with `next_available_date` 2022. Whitney divisions: **166** = Mt. Whitney Trail
(Overnight), **406** = Day Use (All Routes).

## 3. Generic permits: `GET /api/permits/{permit_id}/availability/month`

Params: `start_date=YYYY-MM-01T00:00:00.000Z`, `commercial_acct=false`.

```
payload: { permit_id, next_available_date,
  availability: { "<division_id>": { division_id,
    date_availability: { "<ISO datetime>": { total, remaining, show_walkup, is_secret_quota } },
    quota_type_maps } } }
```
Works for day-use and lottery-style permits; confirmed live for Half Dome (234652). Yosemite (445859) and SEKI (445857) wilderness permits **404 here**; they use
an itinerary-based inventory API that I couldn't confirm, so they aren't supported yet.

## 4. Campgrounds (for reference): `GET /api/camps/availability/campground/{id}/month`

`start_date=YYYY-MM-01T00:00:00.000Z` → `campsites.{id}.availabilities.{ISO date}: "Available" | "Reserved" | "NYR" | ...`

## Behaving politely

- **429 is the throttle.** Retrying extends the block. The client stops for
  `Retry-After` (or 10 min) on the first 429.
- Requests are spaced ≥2 s; polling defaults to every ~5 min with ±15% jitter.
- Honest `User-Agent` naming the tool. Cloud/datacenter IPs are more likely to get
  blocked than a home connection.
- Booking deep link: `https://www.recreation.gov/permits/{id}/registration/detailed-availability?date=YYYY-MM-DD`.
  The tool only alerts; you book by hand (there is no public booking API, and
  automated booking would violate recreation.gov's terms).
