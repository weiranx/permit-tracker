"""Name every land/day-use/itinerary permit and test which availability endpoint answers."""
import json, time, urllib.request, urllib.error
UA = "permit-tracker/0.1 (personal availability watcher)"
def get(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=30)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return "ERR", repr(e)[:200]
B = "https://www.recreation.gov/api"
_, m = get(B + "/permitcontent/permitmapping"); m = m["payload"]
groups = {"land_permit_ids": m["land_permit_ids"]}
for g, ids in groups.items():
    print(f"\n######## {g}")
    for pid in ids:
        if pid.startswith("999"): continue
        c, d = get(f"{B}/permitcontent/{pid}")
        p = d.get("payload", {}) if isinstance(d, dict) else {}
        line = f"{pid}: {c} name={p.get('name')!r} org={p.get('org_name')!r} divs={len(p.get('divisions') or {})} lottery={p.get('has_lottery')} inactive={p.get('is_inactive')}"
        if g == "land_permit_ids":
            for mo in ("2026-11-01&end_date=2026-11-30", "2027-06-01&end_date=2027-06-30"):
                c2, a = get(f"{B}/permitinyo/{pid}/availabilityv2?start_date={mo}&commercial_acct=false")
                if isinstance(a, dict):
                    pl = a.get("payload") or {}
                    rel = sum(1 for dd in pl.values() for v in dd.values() if isinstance(v, dict) and not v.get("not_yet_released"))
                    nz = sum(1 for dd in pl.values() for v in dd.values() if isinstance(v, dict) and (v.get("quota_usage_by_member_daily") or {}).get("remaining"))
                    sample = next((json.dumps(v)[:180] for dd in pl.values() for v in dd.values()), "")
                    line += f"\n    inyo {mo[:7]}: {c2} dates={len(pl)} released={rel} nonzero={nz} sample={sample}"
                else:
                    line += f"\n    inyo {mo[:7]}: {c2} {a}"
                time.sleep(3)
        else:
            c2, a = get(f"{B}/permits/{pid}/availability/month?start_date=2026-11-01T00:00:00.000Z&commercial_acct=false")
            if isinstance(a, dict):
                av = (a.get("payload") or {}).get("availability") or {}
                nd = sum(len(v.get("date_availability") or {}) for v in av.values())
                line += f"\n    permits month: {c2} divisions={len(av)} date_cells={nd}"
            else:
                line += f"\n    permits month: {c2} {a}"
            if g == "itinerary_permit_ids":
                for u in (f"{B}/permititinerary/{pid}/availability/month?month=11&year=2026",
                          f"{B}/permititinerary/{pid}/division/availability?month=11&year=2026"):
                    c3, a3 = get(u)
                    line += f"\n    {u.split('/api')[1][:60]}: {c3} {str(a3)[:160]}"
        print(line, flush=True)
        time.sleep(3)
