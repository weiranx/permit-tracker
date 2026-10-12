"""Hit candidate endpoints and print status + a compact summary. Debug aid only."""
import json, sys, time, urllib.request, urllib.error

UA = "permit-tracker/0.1 (personal availability watcher)"

def summarize(u, body):
    try:
        d = json.loads(body)
    except ValueError:
        return body[:1500]
    p = d.get("payload", d) if isinstance(d, dict) else d
    if "/permitcontent/" in u and isinstance(p, dict):
        divs = p.get("divisions") or {}
        lines = [f"name={p.get('name')!r} divisions={len(divs)} keys={sorted(p)[:40]}"]
        for k, v in list(divs.items())[:80]:
            lines.append(f"  {k}: {v.get('name')!r} code={v.get('code')!r} district={v.get('district')!r} type={v.get('type')!r}")
        return "\n".join(lines)
    if "/permitinyo/" in u and isinstance(p, dict):
        days = sorted(p)
        out = [f"{len(days)} dates: {days[:3]} ... {days[-2:]}"]
        if days:
            first = p[days[0]]
            out.append(f"divisions on {days[0]}: {len(first)}")
            for k, v in list(first.items())[:3]:
                out.append(f"  {k}: {json.dumps(v)[:400]}")
            nz = [(dd, k, v.get('quota_usage_by_member_daily', {}).get('remaining')) for dd in days for k, v in p[dd].items()
                  if isinstance(v, dict) and (v.get('quota_usage_by_member_daily') or {}).get('remaining')]
            out.append(f"nonzero remaining: {len(nz)} e.g. {nz[:5]}")
        return "\n".join(out)
    return body[:1500]

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
    print(f"\n===== {code} {u}\n{summarize(u, body) if code == 200 else body[:800]}")
    time.sleep(2)
