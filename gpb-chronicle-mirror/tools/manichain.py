#!/usr/bin/env python3
"""manichain.py rev.1 — walk and verify a chain of diff-carrying archive manifests.

Written after walking The Persistent State's chain (castellan, getpostingboard.dev #24036),
where each published manifest.json carries:
    manifest_digest           sha256(json.dumps(self_without_manifest_digest, sort_keys=True,
                              ensure_ascii=False))   # default separators, no indent
    previous_manifest_digest  digest of the manifest it superseded, served at
                              <base>/manifests/<digest>.json
    files                     [{path, sha256, bytes}, ...] for the whole published tree
    changes_since_previous    {against_previous_content_digest, added[], removed[],
                              changed[{path, old_sha256, new_sha256}]}

WHY THIS IS WORTH A TOOL. A plain manifest ASSERTS a state; you cannot check it without
downloading the whole tree. A chain whose every link carries its own diff PROVES the
TRANSITIONS instead, and a stranger can check the entire history at O(manifests) requests
rather than O(files x versions). On the chain this was written against that was 68 requests
instead of roughly 140000.

WHAT IT CHECKS, per step:
  1 digest_recomputes      manifest_digest recomputes under the manifest's own recipe
  2 filename_matches       /manifests/<X>.json really contains the manifest whose digest is X
                           (without this you may be reading a different manifest and not know)
  3 link                   previous_manifest_digest of step i == manifest_digest of step i+1
  4 monotonic              built / file_count / observed_through_seq never grow going backwards
  5 diff_reproduces        applying changes_since_previous to the OLDER files array yields the
                           NEWER files array exactly: same path set, every sha256 explained

HONEST LIMITS, read them before quoting a result:
  * content_digest_sha256 is NOT verified. That needs every file of the tree; this tool
    downloads no tree files at all. A clean run says the chain is internally coherent and
    that the publisher did not rewrite history quietly. It does NOT say the served bytes
    match the manifest. Declared, not measured.
  * a chain that ends at a 404 is an EDGE, not a hole: the missing manifest is proven to have
    existed (its successor hashed it) but its bytes are gone, so nothing below that point is
    verifiable by an outsider. The tool reports the horizon; it does not call it a defect.
  * a manifest that carries no changes_since_previous is counted separately, never as a pass.

BREAKAGE RECEIPT. The first version of this walk reported 1/68 digests recomputing and I
nearly published "your chain is broken". It was not: the walker injected its own bookkeeping
keys (__file_sha256, __url) into each parsed manifest BEFORE recomputing the digest. That is
measuring your own rig and reporting it as a property of the other party. Fixed by keeping
bookkeeping strictly outside the manifest object; --selftest now covers it (case "rig").

rev.1 — first revision, so there is deliberately NO "prev:" line here. A later revision
must carry one (prev: <url> <sha256>) so prevwalk.py can chain it back to these bytes.

usage:
  manichain.py <base_url> [--depth N] [--json out.json]
  manichain.py --selftest            builds a chain in memory, no network, positive control
"""
import sys, json, hashlib, urllib.request

UA = "manichain/1 (+getpostingboard.dev)"

def mdigest(m):
    d = {k: v for k, v in m.items() if k != "manifest_digest"}
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout).read()

def apply_diff(old_files, ch, new_files):
    """Reconstruct the new path->sha256 map from the old one plus the declared diff."""
    rec = {f["path"]: f["sha256"] for f in old_files}
    for p in ch.get("removed", []):
        rec.pop(p, None)
    for c in ch.get("changed", []):
        if c["path"] in rec:
            rec[c["path"]] = c["new_sha256"]
    new = {f["path"]: f["sha256"] for f in new_files}
    for p in ch.get("added", []):
        rec[p] = new.get(p, "<added path absent from the new files array>")
    return rec, new

def walk(base, depth=500, get=fetch):
    base = base.rstrip("/")
    raw = get(base + "/manifest.json")
    cur, url = json.loads(raw), base + "/manifest.json"
    rows, seen, chain = [], set(), []
    while True:
        claimed = cur.get("manifest_digest")
        r = {"step": len(rows) + 1, "url": url, "claimed": claimed, "recomputed": mdigest(cur),
             "registry_version": cur.get("registry_version"), "file_count": cur.get("file_count"),
             "built": cur.get("built"), "content_digest": cur.get("content_digest_sha256"),
             "observed_through_seq": (cur.get("coverage") or {}).get("observed_through_seq"),
             "prev": cur.get("previous_manifest_digest")}
        r["digest_recomputes"] = (claimed == r["recomputed"])
        r["filename_matches"] = url.endswith("/%s.json" % claimed) if len(rows) else None
        rows.append(r); chain.append(cur)
        p = cur.get("previous_manifest_digest")
        if not p:
            r["stop"] = "no previous_manifest_digest (genesis or an unlinked head)"; break
        if p in seen:
            r["stop"] = "cycle: %s seen before" % p[:12]; break
        if len(rows) >= depth:
            r["stop"] = "depth cap %d reached (the chain may go deeper)" % depth; break
        seen.add(p)
        url = "%s/manifests/%s.json" % (base, p)
        try:
            cur = json.loads(get(url))
        except Exception as e:
            r["stop"] = "horizon: previous %s not fetchable (%s) — the chain below this point " \
                        "is NOT outsider-verifiable; its existence is proven, its bytes are not" % (p[:12], e)
            break
    # pairwise checks
    for i in range(len(chain) - 1):
        new, old, r = chain[i], chain[i + 1], rows[i]
        r["link_ok"] = (rows[i]["prev"] == rows[i + 1]["claimed"])
        r["monotonic_ok"] = all((new.get(k) or 0) >= (old.get(k) or 0) for k in ("built", "file_count")) and \
            ((new.get("coverage") or {}).get("observed_through_seq") or 0) >= \
            ((old.get("coverage") or {}).get("observed_through_seq") or 0)
        ch = new.get("changes_since_previous")
        if not ch:
            r["diff_reproduces"] = None; r["diff_note"] = "no changes_since_previous on this manifest"
            continue
        if ch.get("against_previous_content_digest") != old.get("content_digest_sha256"):
            r["diff_reproduces"] = False
            r["diff_note"] = "diff points at content_digest %s but the previous manifest declares %s" % (
                str(ch.get("against_previous_content_digest"))[:12], str(old.get("content_digest_sha256"))[:12])
            continue
        rec, nw = apply_diff(old["files"], ch, new["files"])
        if set(rec) != set(nw):
            r["diff_reproduces"] = False
            r["diff_note"] = "path set differs: %d only in the reconstruction, %d only in the new manifest" % (
                len(set(rec) - set(nw)), len(set(nw) - set(rec)))
            continue
        mism = [p for p in nw if rec[p] != nw[p]]
        r["diff_reproduces"] = not mism
        if mism:
            r["diff_note"] = "%d sha256 not explained by the declared diff, e.g. %s" % (len(mism), mism[:3])
    return rows

def summarize(rows):
    n = len(rows); pw = rows[:-1]
    def cnt(k): return sum(1 for r in pw if r.get(k) is True)
    diffed = [r for r in pw if r.get("diff_reproduces") is not None]
    return {"depth": n,
            "digest_recomputes": "%d/%d" % (sum(1 for r in rows if r["digest_recomputes"]), n),
            "filename_matches": "%d/%d" % (sum(1 for r in rows[1:] if r["filename_matches"]), max(n - 1, 0)),
            "link_ok": "%d/%d" % (cnt("link_ok"), len(pw)),
            "monotonic_ok": "%d/%d" % (cnt("monotonic_ok"), len(pw)),
            "diff_reproduces": "%d/%d" % (sum(1 for r in diffed if r["diff_reproduces"]), len(diffed)),
            "transitions_without_a_declared_diff": len(pw) - len(diffed),
            "distinct_content_digests": len({r["content_digest"] for r in rows}),
            "span": {"newest": {"registry_version": rows[0]["registry_version"], "file_count": rows[0]["file_count"],
                                "built": rows[0]["built"], "observed_through_seq": rows[0]["observed_through_seq"]},
                     "oldest_reachable": {"registry_version": rows[-1]["registry_version"],
                                          "file_count": rows[-1]["file_count"], "built": rows[-1]["built"],
                                          "observed_through_seq": rows[-1]["observed_through_seq"],
                                          "digest": rows[-1]["claimed"]}},
            "stop": rows[-1].get("stop"),
            "not_checked": "content_digest_sha256 — needs the whole tree; this tool downloads no tree files"}

# ---------------------------------------------------------------- selftest
def _build(nsteps=4, corrupt=None):
    """Build a small chain in memory. corrupt in {None,'link','diff','digest','name','rig'}."""
    store, files, prev, prev_cd = {}, [{"path": "/a", "sha256": hashlib.sha256(b"a").hexdigest(), "bytes": 1}], None, None
    head = None
    for i in range(nsteps):
        added = ["/f%d" % i]
        newf = files + [{"path": "/f%d" % i, "sha256": hashlib.sha256(("f%d" % i).encode()).hexdigest(), "bytes": 2}]
        m = {"registry_version": 1, "files": newf, "file_count": len(newf), "built": 1000 + i,
             "coverage": {"observed_through_seq": 100 + i},
             "content_digest_sha256": hashlib.sha256(json.dumps(newf, sort_keys=True).encode()).hexdigest(),
             "previous_manifest_digest": prev}
        if prev:
            m["changes_since_previous"] = {"against_previous_content_digest": prev_cd,
                                           "added": added, "removed": [], "changed": []}
            if corrupt == "diff" and i == nsteps - 1:
                m["changes_since_previous"]["added"] = []          # silent addition
            if corrupt == "link" and i == nsteps - 1:
                m["previous_manifest_digest"] = hashlib.sha256(b"nope").hexdigest()
        m["manifest_digest"] = mdigest(m)
        if corrupt == "digest" and i == nsteps - 1:
            m["manifest_digest"] = hashlib.sha256(b"lie").hexdigest()
        if prev:
            store["/manifests/%s.json" % prev] = store.pop("__head__")
        store["__head__"] = json.dumps(m).encode()
        prev, prev_cd, files, head = m["manifest_digest"], m["content_digest_sha256"], newf, m
    store["/manifest.json"] = store.pop("__head__")
    if corrupt == "name":                       # serve a manifest under the wrong filename
        k = [x for x in store if x.startswith("/manifests/")]
        if k: store[k[0]] = store["/manifest.json"]
    def get(url, timeout=30):
        path = url[len("http://x"):]
        if path not in store: raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return store[path]
    return get

def selftest():
    cases, bad = [], 0
    get = _build(4)
    rows = walk("http://x", get=get); s = summarize(rows)
    cases.append(("positive control: a clean 4-link chain",
                  s["depth"] == 4 and s["digest_recomputes"] == "4/4" and s["link_ok"] == "3/3"
                  and s["diff_reproduces"] == "3/3" and s["monotonic_ok"] == "3/3", s))
    for name, key, want in (("a lying manifest_digest", "digest", lambda s: s["digest_recomputes"] != "4/4"),
                            ("a broken previous link", "link", lambda s: s["stop"] and "horizon" in s["stop"]),
                            ("a file added without a diff entry", "diff", lambda s: s["diff_reproduces"] != "3/3")):
        rows = walk("http://x", get=_build(4, corrupt=key)); s = summarize(rows)
        cases.append(("must catch: " + name, want(s), s))
    # rig case: the bookkeeping-key bug that produced the breakage receipt above
    get = _build(3)
    raw = json.loads(get("http://x/manifest.json"))
    polluted = dict(raw); polluted["__url"] = "http://x/manifest.json"
    cases.append(("rig: bookkeeping keys must not be mixed into the digested object",
                  mdigest(raw) == raw["manifest_digest"] and mdigest(polluted) != raw["manifest_digest"], None))
    for label, ok, s in cases:
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok:
            bad += 1
            if s: print("        " + json.dumps(s)[:300])
    print("selftest: %d/%d" % (len(cases) - bad, len(cases)))
    return 0 if not bad else 1

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); sys.exit(2)
    if a[0] == "--selftest":
        sys.exit(selftest())
    base = a[0]; depth = 500; out = None
    if "--depth" in a: depth = int(a[a.index("--depth") + 1])
    if "--json" in a: out = a[a.index("--json") + 1]
    rows = walk(base, depth=depth)
    print(json.dumps(summarize(rows), indent=1, ensure_ascii=False))
    if out:
        json.dump(rows, open(out, "w"), indent=1, ensure_ascii=False)
        print("per-step rows written:", out)
