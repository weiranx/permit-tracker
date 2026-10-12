"""Hit candidate endpoints and print status + body head. Debug aid only."""
import json, sys, time, urllib.request, urllib.error

UA = "permit-tracker/0.1 (personal availability watcher)"
urls = [l.strip() for l in open(sys.argv[1]) if l.strip() and not l.startswith("#")]
for u in urls:
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            code, body = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code, body = e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        code, body = "ERR", repr(e)
    print(f"\n===== {code} {u}\n{body[:2500]}")
    time.sleep(2)
