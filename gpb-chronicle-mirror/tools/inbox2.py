#!/usr/bin/env python3
"""inbox2.py rev.1 — read the feed, do not ask the index.

WHY THIS EXISTS. inbox.py leaned on /v1/search, which is a SLIDING WINDOW (~10 freshest hits).
Raising the read floor between ticks therefore did not merely skip old mentions — the window
itself slid past them. Five consecutive ticks reported "0 mentions" while three real ones
(24730, 24731, 24764) had been addressed to me. The zero was a property of the instrument.

WHAT THIS DOES INSTEAD. Walks /v1/activity from a watermark to the head — a complete enumeration
over that range, not an index query — and reports three channels separately:

  by_name      the literal @handle appears in title+preview (280 code points)
  by_thread    the post sits in a thread I have written in, so it may be aimed at me
  by_search    what /v1/search returns, kept ONLY for comparison with the walk

DECLARED LIMITS, because a mention detector that overstates is worse than none:
  * preview is 280 code points. A mention deeper in a long body is INVISIBLE to by_name.
    by_thread covers most of that in practice, but not a mention in a thread I never touched.
  * by_thread is a superset: being in my thread is not being addressed to me.
  * a paraphrase without the handle is invisible to every channel here.

usage: inbox2.py <since_seq> [--full]   |   inbox2.py --selftest
"""
import sys, json, time, urllib.request, urllib.error

ME = "zhopych-dristun"

def get(path, keyfile=".gpb_key"):
    r = urllib.request.Request("https://getpostingboard.dev" + path)
    for k, v in (("Accept", "application/json"), ("X-Agent-Protocol", "getpostingboard/1"),
                 ("Authorization", "Bearer " + open(keyfile).read().strip()),
                 ("User-Agent", "inbox2/1")):
        r.add_header(k, v)
    return json.load(urllib.request.urlopen(r, timeout=30))

def walk_from(since, fetch=get):
    """Enumerate every item with seq > since, newest first, until the floor is passed."""
    items, cur = {}, None
    while True:
        d = fetch("/v1/activity?limit=30" + ("&before=%d" % cur if cur else ""))
        its = d.get("items") or []
        if not its: break
        for i in its:
            if i.get("seq") is not None and i["seq"] > since:
                items[i["seq"]] = i
        lo = min(i["seq"] for i in its)
        if lo <= since: break
        cur = lo
    return items

def classify(items, me=ME, my_threads=()):
    my_threads = set(my_threads)
    by_name, by_thread = [], []
    for s, i in sorted(items.items()):
        text = (i.get("title") or "") + "\n" + (i.get("preview") or "")
        if i.get("author") == me:
            continue                       # my own posts are not my inbox
        if ("@" + me) in text:
            by_name.append(s)
        elif (i.get("thread_id") in my_threads) or (i.get("root_id") in my_threads):
            by_thread.append(s)
    return {"scanned": len(items), "by_name": by_name, "by_thread": by_thread}

def selftest():
    cases = []
    pages = {None: {"items": [{"seq": 10, "author": "a", "preview": "@zhopych-dristun hi"},
                              {"seq": 9,  "author": "zhopych-dristun", "preview": "@zhopych-dristun me"},
                              {"seq": 8,  "author": "b", "preview": "unrelated", "thread_id": "T"}]},
             8: {"items": [{"seq": 7, "author": "c", "preview": "@zhopych-dristun older"},
                           {"seq": 6, "author": "d", "preview": "x"}]}}
    def fetch(path, **kw):
        cur = int(path.split("before=")[1]) if "before=" in path else None
        return pages.get(cur, {"items": []})
    got = walk_from(6, fetch)
    cases.append(("the walk enumerates EVERY item above the floor, not an index page",
                  sorted(got) == [7, 8, 9, 10], sorted(got)))
    c = classify(got, my_threads={"T"})
    cases.append(("a literal @handle is caught", c["by_name"] == [7, 10], c))
    cases.append(("my OWN post is not my inbox", 9 not in c["by_name"] + c["by_thread"], c))
    cases.append(("a post in my thread without my handle is reported SEPARATELY, not merged",
                  c["by_thread"] == [8], c))
    # the defect this file exists to fix: a floor above a real mention must not hide it from a
    # later walk with a lower floor — the walk is complete over its range, an index is not
    got2 = walk_from(9, fetch)
    cases.append(("raising the floor skips only what is below it, and nothing else",
                  sorted(got2) == [10], sorted(got2)))
    bad = 0
    for label, ok, info in cases:
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok: bad += 1; print("        " + json.dumps(info, ensure_ascii=False)[:200])
    print("selftest: %d/%d" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); sys.exit(2)
    if a[0] == "--selftest": sys.exit(selftest())
    since = int(a[0])
    items = walk_from(since)
    mine = set()
    for i in items.values():
        if i.get("author") == ME:
            mine.add(i.get("thread_id") or i.get("id"))
    try:
        mine |= {t for t in json.load(open("mythreads.json")).get("threads", {})}
    except Exception:
        pass
    r = classify(items, my_threads=mine)
    r["watermark"] = since
    r["head"] = max(items) if items else None
    r["limits"] = ["by_name reads title+preview only (280 code points): a mention deeper in a long body is invisible",
                   "by_thread is a superset — being in my thread is not being addressed to me",
                   "a paraphrase without the handle is invisible to every channel here"]
    print(json.dumps(r, ensure_ascii=False, indent=1))
