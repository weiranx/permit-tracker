"""Grep JS bundles for context around 'permititinerary' and 'availability'."""
import re, time, urllib.request
UA = "Mozilla/5.0 (permit-tracker research)"
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8", "replace")
html = get("https://www.recreation.gov/permits/445859")
for s in sorted(set(re.findall(r'src="(/[^"]+\.js)"', html))):
    try: js = get("https://www.recreation.gov" + s)
    except Exception: continue
    for kw in ("permititinerary", "permitinyo", "itinerary/", "availability/month", "permitavailability"):
        for m in list(re.finditer(re.escape(kw), js))[:12]:
            print(f"[{s.split('/')[-1][:30]}] {kw}: ...{js[max(0,m.start()-160):m.end()+160]!r}")
    time.sleep(0.5)
