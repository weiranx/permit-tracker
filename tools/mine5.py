"""Itinerary bundle API paths + permit season info. Debug aid."""
import json, re, time, urllib.request, urllib.error
UA = "Mozilla/5.0 (permit-tracker research)"
def raw(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"}), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
c, html = raw("https://www.recreation.gov/permits/4675321")
mains = sorted(set(re.findall(r'src="(/[^"]+\.js)"', html)))
print("itinerary mains:", mains)
seen = set()
for s in mains:
    c, js = raw("https://www.recreation.gov" + s)
    for m in re.findall(r'`(/api/[^`]{0,200})`|"(/api/[^"]{0,200})"', js):
        p = m[0] or m[1]
        if p not in seen and ("permit" in p or "itinerar" in p):
            seen.add(p); print("  ", p)
    time.sleep(1)
B = "https://www.recreation.gov/api"
for u in [f"{B}/permitseason/display/445859/2026-11-15", f"{B}/permitseason/display/445859/2027-06-15",
          f"{B}/permitseason/display/445860/2027-06-15", f"{B}/permitseason/display/445857/2027-06-15",
          f"{B}/permitseason/display/445859/2026-11-15T00:00:00Z"]:
    c, b = raw(u); print(f"\n== {c} {u}\n{b[:1500]}"); time.sleep(3)
c, b = raw(f"{B}/permitcontent/445859")
try:
    p = json.loads(b)["payload"]
    print("\nYosemite important_dates:", json.dumps(p.get("important_dates"))[:2000])
    print("Yosemite lotteries:", json.dumps(p.get("lotteries"))[:1500])
    print("launch window:", p.get("launch_window_open"), p.get("launch_window_close"), p.get("launch_window_step"))
except Exception as e:
    print("parse fail", e)
