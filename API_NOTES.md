# How recreation.gov loads permit availability

The permit pages are a React app. The calendar and trailhead grid aren't rendered on
the server; the browser calls unauthenticated JSON endpoints under
`https://www.recreation.gov/api/`. No API key, no login, and none of it is documented.
The official RIDB API (`ridb.recreation.gov`) has facility metadata but **no availability**.

## Where these notes come from

The sandbox this was built in can't reach recreation.gov (blocked by its network
policy), so nothing here was captured live by me. It's assembled from the source of
open-source clients that call these endpoints today:

- [mdeckebach/recdotgov](https://github.com/mdeckebach/recdotgov): Inyo permit snapshots (`permitinyo`, `permitcontent`)
- [JamalMansuri/campsiterecon](https://github.com/JamalMansuri/campsiterecon): `references/api-response-shapes.md`, checked live 2026-09-20
- [camply discussion #22](https://github.com/juftin/camply/discussions/22): generic `permits` endpoint

Run `python3 -m permit_tracker divisions 233260` first on your machine to confirm.

## 1. Permit metadata: `GET /api/permitcontent/{permit_id}`

```
payload.name
payload.divisions: { "<division_id>": { id, name, code, district, description,
                                         latitude, longitude, permit_id, version } }
```
A **division** is a trailhead / entry point / zone; it's the unit quotas are set on.

## 2. Inyo-style quota permits: `GET /api/permitinyo/{permit_id}/availabilityv2`

Params: `start_date=YYYY-MM-DD`, `end_date=YYYY-MM-DD`, `commercial_acct=false`.
The tracker requests one calendar month per call.

```
payload: { "<YYYY-MM-DD>": { "<division_id>": {
    quota_usage_by_member_daily: { total, remaining },
    is_walkup, not_yet_released, release_date } } }
```
Used by Mt. Whitney (233260), Inyo NF wilderness (233262), Sierra NF (445858) and
other Sierra wilderness permits. The date is the **entry date**; `remaining` is
people (or groups, depending on permit) left on that trailhead's quota.
`is_walkup: true` rows are the in-person quota and can't be booked online.

## 3. Generic permits: `GET /api/permits/{permit_id}/availability/month`

Params: `start_date=YYYY-MM-01T00:00:00.000Z`, `commercial_acct=false`.

```
payload: { permit_id, next_available_date,
  availability: { "<division_id>": { division_id,
    date_availability: { "<ISO datetime>": { total, remaining, show_walkup, is_secret_quota } },
    quota_type_maps } } }
```
Works for day-use and lottery-style permits (e.g. Half Dome 234652, Central Cascades
4675311). Yosemite (445859) and SEKI (445857) wilderness permits **404 here**; they use
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
