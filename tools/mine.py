"""Pull recreation.gov's JS bundles and list permit-related API paths. Debug aid."""
import re, sys, time, urllib.request
UA = "Mozilla/5.0 (permit-tracker research)"
def get(u):
    r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30)
    return r.read().decode("utf-8", "replace")
html = get("https://www.recreation.gov/permits/445859")
scripts = sorted(set(re.findall(r'src="(/[^"]+\.js)"', html)))
print("scripts:", len(scripts))
paths = {}
for s in scripts:
    try:
        js = get("https://www.recreation.gov" + s)
    except Exception as e:
        print("fail", s, e); continue
    for m in re.findall(r'["`\'](/?api/permit[a-z]*/[^"`\']{0,160})["`\']', js):
        paths.setdefault(m, s)
    for m in re.findall(r'["`\']((?:/api)?/permit(?:itinerary|inyo|s|content|availability|lottery)[^"`\']{0,160})["`\']', js):
        paths.setdefault(m, s)
    time.sleep(0.5)
for p in sorted(paths):
    print(p)
# also template-literal pieces like "permititinerary/".concat(
for s in scripts[:0]:
    pass
