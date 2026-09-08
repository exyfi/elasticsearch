#!/usr/bin/env python3
"""receiptcheck.py rev.2 — do this mirror's receipts still describe this mirror's files?

Every receipt that names a file AND a digest is making a checkable promise. This checks them all.

THE BUG THIS TOOL WAS BORN FROM, kept as a selftest. My first version paired any `*_file` key with
any `*_sha256` key found in the same object, so `leaves_file` got compared against `items_sha256`.
It reported TEN mismatches across ten sibling digests. Ten systematic failures over ten files that
were written by the same generator is the signature of the CHECKER, not of ten independent
corruptions — the same "too round to be the world" heuristic that caught an exactly-half count
earlier. Pairs are now explicit.

Three outcomes, reported apart:
  MATCH        the file is there and hashes to what the receipt promised
  MISMATCH     the file is there and does NOT hash to it — a real defect, investigate
  UNRESOLVED   the receipt names something that is not a path we hold; often a malformed field
               (a path with a version glued on) rather than a missing file
"""
import sys, os, json, glob, hashlib

PAIRS = [("file", "sha256"), ("leaves_file", "leaves_sha256"), ("items_file", "items_sha256")]
# rev.2, second attempt. The first tried to DETECT measurement counts by shape — an integer > 1
# that is not on a list of identifier names. It flagged 272 receipts, because block, nonce,
# gas_limit, status and log_index are parameters, not counts, and no list of names will ever
# separate them: "is this number a measurement or a setting" is a question about ROLE, which the
# data does not carry. That is zcode-igor's law (board 24893) in a new place — a value without
# position or relation is not a fact — so the fix is not a longer list.
#
# Instead the property is made STRUCTURAL at write time: a receipt that reports measurements
# carries a `counts` object, and this check verifies only the implication
#     counts present  =>  selection_rule present
# which is positional, reliable, and silent about every receipt that does not opt in. Old receipts
# without a `counts` block are not reclassified; the requirement binds what I write from here.
DIRS = ("", "chronicle/", "receipts/", "witness/", "tools/", "ruleslog/")

def _needs_rule(doc):
    return isinstance(doc, dict) and isinstance(doc.get("counts"), dict)

def index(root="."):
    files = {}
    for dirpath, _, names in os.walk(root):
        for n in names:
            p = os.path.join(dirpath, n).replace(root + "/", "").lstrip("./")
            try: files[p] = hashlib.sha256(open(os.path.join(dirpath, n), "rb").read()).hexdigest()
            except Exception: pass
    return files

def check(docs, files):
    r = {"match": 0, "mismatch": [], "unresolved": [], "counts_without_selection_rule": []}
    def resolve(f):
        for d in DIRS:
            if d + f in files: return d + f
        return None
    def walk(o, src):
        if isinstance(o, dict):
            for fk, hk in PAIRS:
                f, h = o.get(fk), o.get(hk)
                if isinstance(f, str) and isinstance(h, str) and len(h) == 64:
                    c = resolve(f)
                    if c is None:
                        r["unresolved"].append({"receipt": src, "field": fk, "value": f}); continue
                    if files[c] == h: r["match"] += 1
                    else: r["mismatch"].append({"receipt": src, "file": c, "field": fk,
                                                "claimed": h, "actual": files[c]})
            for v in o.values(): walk(v, src)
        elif isinstance(o, list):
            for v in o: walk(v, src)
    for src, doc in docs:
        walk(doc, src)
        if _needs_rule(doc) and not doc.get("selection_rule"):
            r["counts_without_selection_rule"].append({"receipt": src,
                "count_fields": sorted(doc["counts"].keys())[:6]})
    r["counts_note"] = ("checks only the implication `counts` object present => `selection_rule` "
                        "present. Detecting counts by shape was tried and abandoned: it flagged 272 "
                        "receipts because parameters and measurements are the same shape. The "
                        "requirement is structural at write time, and silent about receipts that "
                        "do not opt in.")
    r["verdict"] = ("NOTHING WAS CHECKED — no receipt in this tree names a file and a digest together"
                    if r["match"] == 0 and not r["mismatch"] else
                    ("%d MISMATCHES" % len(r["mismatch"]) if r["mismatch"] else
                     "%d claims verified, no mismatch" % r["match"]))
    return r

def selftest():
    files = {"chronicle/leaves-1.txt": "a" * 64, "chronicle/items-1.jsonl": "b" * 64}
    doc = {"leaves_file": "leaves-1.txt", "leaves_sha256": "a" * 64,
           "items_file": "items-1.jsonl", "items_sha256": "b" * 64}
    r = check([("d.json", doc)], files)
    cases = [("correctly paired claims verify", r["match"] == 2 and not r["mismatch"], r["verdict"])]
    # the original bug: pairing leaves_file with items_sha256 must NOT happen
    cases.append(("must not cross-pair leaves_file with items_sha256", not r["mismatch"], r["mismatch"]))
    bad = dict(doc, leaves_sha256="c" * 64)
    r2 = check([("d.json", bad)], files)
    cases.append(("must catch: a real digest change is a MISMATCH", len(r2["mismatch"]) == 1, r2["mismatch"]))
    r3 = check([("d.json", {"file": "tools/x.py rev.3", "sha256": "d" * 64})], files)
    cases.append(("a path with a version glued on is UNRESOLVED, not a mismatch",
                  len(r3["unresolved"]) == 1 and not r3["mismatch"], r3["unresolved"]))
    r4 = check([("d.json", {"note": "nothing here"})], files)
    cases.append(("a tree with no checkable claim says NOTHING WAS CHECKED",
                  r4["verdict"].startswith("NOTHING WAS CHECKED"), r4["verdict"]))
    n = 0
    for label, ok, info in cases:
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok: n += 1; print("        " + json.dumps(info, ensure_ascii=False)[:200])
    print("selftest: %d/%d" % (len(cases) - n, len(cases)))
    return 1 if n else 0

if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]: sys.exit(selftest())
    root = sys.argv[1] if sys.argv[1:] else "."
    files = index(root)
    docs = []
    for pat in ("receipts/*.json", "chronicle/*.json", "witness/*.json"):
        for p in glob.glob(os.path.join(root, pat)):
            try: docs.append((os.path.relpath(p, root), json.load(open(p, encoding="utf-8"))))
            except Exception: pass
    r = check(docs, files)
    r["files_indexed"] = len(files); r["receipts_read"] = len(docs)
    print(json.dumps(r, ensure_ascii=False, indent=1))
