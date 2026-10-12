"""Find lazy-loaded chunks and grep them for permit API paths. Debug aid."""
import json, re, time, urllib.request
UA = "Mozilla/5.0 (permit-tracker research)"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30).read().decode("utf-8", "replace")
html = get("https://www.recreation.gov/permits/4675321")
mains = sorted(set(re.findall(r'src="(/[^"]+\.js)"', html)))
chunks = set()
for s in mains:
    js = get("https://www.recreation.gov" + s)
    base = s.rsplit("/", 1)[0]
    for c in re.findall(r'["\'`](?:\./|assets/|/assets/)?([A-Za-z0-9_\-]+-[A-Za-z0-9_\-]{6,}\.js)["\'`]', js):
        chunks.add(base + "/" + c)
print("chunks found:", len(chunks))
interesting = [c for c in chunks if re.search(r"ermit|tinerar|ilderness|ottery|vailab", c, re.I)]
print("interesting:", interesting[:40])
order = interesting + [c for c in sorted(chunks) if c not in interesting]
found = {}
for i, c in enumerate(order[:60]):
    try:
        js = get("https://www.recreation.gov" + c)
    except Exception as e:
        continue
    for m in re.findall(r'`(/api/[a-z]+/[^`]{0,180})`|"(/api/[a-z]+/[^"]{0,180})"', js):
        p = m[0] or m[1]
        if "permit" in p and p not in found:
            found[p] = c
            print(f"{c.split('/')[-1]}: {p}")
    for kw in ("itinerary", "/availability"):
      if kw in js and False:
        for m in list(re.finditer("permititinerary", js))[:15]:
            print(f"  CTX {c.split('/')[-1]}: {js[max(0,m.start()-200):m.end()+200]!r}")
    time.sleep(0.2)
import sys; sys.exit(0)
try:
    print(get("https://www.recreation.gov/api/permitcontent/permitmapping")[:4000])
except Exception as e:
    print("ERR", e)
