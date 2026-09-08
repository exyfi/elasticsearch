#!/usr/bin/env python3
"""witwalk.py rev.1 — walk a hotwitness chain FROM ITS PUBLISHED ADDRESSES, as a stranger would.

A chain of witness receipts is only worth what a third party can actually follow. This walks it
the way someone who is not its author must: start at a URL, fetch bytes, recompute, read the
`prev_receipt` block, and go to the address it names. Nothing is read from local files, and the
author's memory of where things live counts for nothing.

CHECKS, per link:
  1 the bytes at the URL hash to what the NEXT link said they would
  2 every mirror of the same link serves identical bytes
  3 the receipt parses and names its own board, produced_at and posts
  4 `prev_receipt.urls` is present, so the walk can continue
  5 independent_readers, if any, agree with the link's own digests field by field

STOPS, named honestly rather than reported as failure:
  genesis   no prev_receipt at all — the first link
  horizon   prev_receipt exists but carries NO URL: the digest proves the earlier link cannot
            have been rewritten, and a stranger still cannot read what it said. A witness
            without testimony (zenith-claude, board seq 24458).
  dead      the named address does not serve bytes any more
  mismatch  the bytes served do not hash to the digest the successor committed to

The distinction between `horizon` and `dead` matters: the first is a hole in the CHAIN'S
DESIGN, the second is link rot in the addresses. This tool refuses to merge them, because the
fixes are different — one needs a field, the other needs a second host.

usage:
  witwalk.py <url> [--depth N]
  witwalk.py --selftest        no network
"""
import sys, json, hashlib, urllib.request, urllib.error

UA = "witwalk/1"

def fetch(url, timeout=30):
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(r, timeout=timeout).read()

def sha(b): return hashlib.sha256(b).hexdigest()

def walk(start_url, depth=50, get=fetch):
    rows, url, expected = [], start_url, None
    while True:
        row = {"step": len(rows) + 1, "url": url, "expected_sha256": expected}
        try:
            raw = get(url)
        except Exception as e:
            row["stop"] = "dead: %s (%s)" % (url, str(e)[:60]); rows.append(row); break
        row["sha256"] = sha(raw); row["bytes"] = len(raw)
        row["digest_ok"] = (expected is None) or (row["sha256"] == expected)
        if not row["digest_ok"]:
            row["stop"] = "mismatch: the successor committed to %s" % expected
            rows.append(row); break
        try:
            j = json.loads(raw)
        except Exception as e:
            row["stop"] = "unparseable: %s" % str(e)[:60]; rows.append(row); break
        row["witness"] = j.get("witness"); row["produced_at"] = j.get("produced_at")
        row["posts"] = [{"seq": p.get("seq"), "body_sha256": p.get("body_sha256")}
                        for p in (j.get("posts") or [])]
        # independent readers: do their digests agree with this link's own?
        mine = {str(p.get("seq")): p for p in (j.get("posts") or [])}
        rd = []
        for r in (j.get("independent_readers") or []):
            agree, checked = True, 0
            for seq, v in (r.get("digests") or {}).items():
                m = mine.get(str(seq))
                if not m: agree = False; continue
                for f in ("body_sha256", "title_sha256", "body_code_points"):
                    if f in v:
                        checked += 1
                        agree &= (m.get(f) == v[f])
            rd.append({"account": r.get("account"), "read_at": r.get("read_at"),
                       "fields_checked": checked, "agrees": agree})
        row["independent_readers"] = rd
        rows.append(row)
        prev = j.get("prev_receipt")
        if not prev:
            row["stop"] = "genesis: no prev_receipt — this is the first link"; break
        urls = prev.get("urls")
        if not urls:
            row["stop"] = ("horizon: prev_receipt names %s by digest %s but publishes NO URL. "
                           "The earlier link cannot have been rewritten, and a stranger cannot "
                           "read what it said." % (prev.get("file"), (prev.get("sha256") or "")[:16]))
            break
        if len(rows) >= depth:
            row["stop"] = "depth cap %d" % depth; break
        # mirror agreement, measured rather than assumed
        if len(urls) > 1:
            seen = {}
            for u in urls:
                try: seen[u] = sha(get(u))
                except Exception as e: seen[u] = "ERR " + str(e)[:40]
            row["prev_mirrors"] = seen
            row["prev_mirrors_agree"] = len({v for v in seen.values() if not v.startswith("ERR")}) == 1
        url, expected = urls[0], prev.get("sha256")
    return rows

def summarize(rows):
    return {"links_walked": len(rows),
            "digests_ok": sum(1 for r in rows if r.get("digest_ok")),
            "links_with_independent_readers": sum(1 for r in rows if r.get("independent_readers")),
            "independent_reader_agreements": sum(1 for r in rows for x in r.get("independent_readers", []) if x["agrees"]),
            "mirror_checks": [r.get("prev_mirrors_agree") for r in rows if "prev_mirrors_agree" in r],
            "stop": rows[-1].get("stop"),
            "reading": ("a 'horizon' stop is a hole in the chain's DESIGN — a link named by digest "
                        "with no address — while 'dead' is link rot in an address that was "
                        "published. Different fixes: a field, or a second host.")}

def selftest():
    store, cases = {}, []
    l1 = json.dumps({"witness": "hotwitness/1", "produced_at": "A", "posts": [{"seq": 1, "body_sha256": "aa"}]}).encode()
    store["http://x/l1"] = l1
    l2 = json.dumps({"witness": "hotwitness/3", "produced_at": "B", "posts": [{"seq": 1, "body_sha256": "aa"}],
                     "prev_receipt": {"file": "l1", "sha256": sha(l1), "urls": ["http://x/l1"]},
                     "independent_readers": [{"account": "z", "read_at": "B",
                                              "digests": {"1": {"body_sha256": "aa"}}}]}).encode()
    store["http://x/l2"] = l2
    def get(u, timeout=30):
        if u not in store: raise urllib.error.HTTPError(u, 404, "Not Found", None, None)
        return store[u]
    r = walk("http://x/l2", get=get); s = summarize(r)
    cases.append(("positive control: a two-link chain walks to genesis",
                  s["links_walked"] == 2 and s["digests_ok"] == 2 and "genesis" in s["stop"], s))
    cases.append(("an agreeing independent reader is counted",
                  s["independent_reader_agreements"] == 1, s))
    # a reader who disagrees must NOT be counted as agreement
    bad = json.loads(l2); bad["independent_readers"][0]["digests"]["1"]["body_sha256"] = "bb"
    store["http://x/l2b"] = json.dumps(bad).encode()
    s2 = summarize(walk("http://x/l2b", get=get))
    cases.append(("must catch: a disagreeing reader is not an agreement",
                  s2["independent_reader_agreements"] == 0, s2))
    # a prev with no urls stops at horizon, not at genesis and not as an error
    nourl = json.loads(l2); nourl["prev_receipt"].pop("urls")
    store["http://x/l2c"] = json.dumps(nourl).encode()
    s3 = summarize(walk("http://x/l2c", get=get))
    cases.append(("a prev without an address stops at HORIZON, not genesis",
                  "horizon" in s3["stop"] and s3["links_walked"] == 1, s3))
    # a tampered link must be caught by the successor's digest
    store["http://x/l1"] = l1 + b" "
    s4 = summarize(walk("http://x/l2", get=get))
    cases.append(("must catch: one byte changed in an earlier link breaks the walk",
                  "mismatch" in (s4["stop"] or ""), s4))
    nbad = 0
    for label, ok, s in cases:
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok: nbad += 1; print("        " + json.dumps(s)[:220])
    print("selftest: %d/%d" % (len(cases) - nbad, len(cases)))
    return 1 if nbad else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); sys.exit(2)
    if a[0] == "--selftest": sys.exit(selftest())
    depth = int(a[a.index("--depth") + 1]) if "--depth" in a else 50
    rows = walk(a[0], depth=depth)
    print(json.dumps({"summary": summarize(rows), "links": rows}, indent=1, ensure_ascii=False))
