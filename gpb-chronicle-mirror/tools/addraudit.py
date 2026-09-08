#!/usr/bin/env python3
"""addraudit.py rev.1 — read back every published address and report what is single or dead.

An address index is a promise. This checks it the only way a promise can be checked: fetch each
address and compare the bytes against the digest recorded beside it. Two failures are reported
apart, because the fixes differ:
  DEAD    the address serves nothing any more -> needs a new host
  DRIFT   it serves something, but not what was recorded -> needs investigation, not a re-upload
  SINGLE  the artefact has exactly one live address -> one host away from unreachable
"""
import sys, hashlib, urllib.request, urllib.error, collections, json, time

def fetch(url, timeout=25):
    r = urllib.request.Request(url, headers={"User-Agent": "addraudit/1"})
    return urllib.request.urlopen(r, timeout=timeout).read()

def audit(lines, get=fetch):
    by = collections.defaultdict(list)
    rows = []
    for ln in lines:
        p = ln.split(None, 2)
        if len(p) < 2 or len(p[0]) != 64: continue
        digest, url = p[0], p[1]
        label = p[2].strip() if len(p) > 2 else ""
        try:
            b = get(url); got = hashlib.sha256(b).hexdigest()
            st = "OK" if got == digest else "DRIFT"
        except Exception as e:
            got, st = None, "DEAD"
        rows.append({"digest": digest, "url": url, "label": label, "status": st, "served": got})
        if st == "OK": by[digest].append(url)
    singles = sorted({d for d, us in by.items() if len(us) == 1})
    return {"checked": len(rows),
            "ok": sum(1 for r in rows if r["status"] == "OK"),
            "dead": [r for r in rows if r["status"] == "DEAD"],
            "drift": [r for r in rows if r["status"] == "DRIFT"],
            "artefacts": len(by),
            "single_address_artefacts": [{"digest": d, "url": by[d][0],
                                          "label": next((r["label"] for r in rows if r["digest"] == d and r["status"] == "OK"), "")}
                                         for d in singles],
            "note": "DEAD needs a second host; DRIFT needs investigation, never a silent re-upload; "
                    "SINGLE is one host away from unreachable and is not yet a failure."}

def selftest():
    store = {"http://a": b"x", "http://b": b"x", "http://c": b"y"}
    def get(u, timeout=25):
        if u not in store: raise urllib.error.HTTPError(u, 404, "gone", None, None)
        return store[u]
    hx = hashlib.sha256(b"x").hexdigest(); hy = hashlib.sha256(b"y").hexdigest()
    lines = ["%s http://a two-host" % hx, "%s http://b two-host" % hx,
             "%s http://c only-one" % hy, "%s http://missing rotted" % hy,
             "%s http://c wrong-digest" % hx]
    r = audit(lines, get)
    cases = [("a two-host artefact is not reported as single",
              all(s["digest"] != hx for s in r["single_address_artefacts"]), r["single_address_artefacts"]),
             ("a one-host artefact IS reported as single",
              any(s["digest"] == hy for s in r["single_address_artefacts"]), r["single_address_artefacts"]),
             ("a missing address is DEAD", len(r["dead"]) == 1 and r["dead"][0]["url"] == "http://missing", r["dead"]),
             ("must catch: a live address serving the WRONG bytes is DRIFT, not OK",
              len(r["drift"]) == 1 and r["drift"][0]["url"] == "http://c", r["drift"]),
             ("DEAD and DRIFT are never merged", r["dead"] and r["drift"] and r["dead"] != r["drift"], None)]
    bad = 0
    for label, ok, info in cases:
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok: bad += 1; print("        " + json.dumps(info, ensure_ascii=False)[:200])
    print("selftest: %d/%d" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--selftest": sys.exit(selftest())
    lines = open(a[0] if a else "heartbeat.txt", encoding="utf-8").read().splitlines()
    r = audit(lines)
    r["audited_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(json.dumps(r, ensure_ascii=False, indent=1))
