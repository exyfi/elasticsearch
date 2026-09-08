#!/usr/bin/env python3
"""addenda.py rev.1 — build the FORWARD index that corrections do not carry themselves.

An addendum names its parent; a parent does not name its addendum. So a reader who opens the
corrected file has no way to learn it was corrected — the correction exists and is unreachable
from the thing it corrects. That is the same defect as an undeclared hole, one level up: not a
missing fact, a missing pointer.

Published files are NOT edited to add the pointer, because editing a published artefact to fix
its metadata is exactly what this mirror refuses to do. Instead the map is derived, and it is
derived rather than maintained so that it cannot go stale.

Every key that has been used to name a parent is checked, because an index that silently omits
an entry is worse than no index: PARENT_KEYS below is the whole list, and an addendum naming a
parent by some other key shows up as an ORPHAN rather than being dropped.
"""
import sys, os, json, glob

# `of_digest` is here because chronicle/digest-011-addendum-001.json names its parent that way.
# That file is PUBLISHED to paste hosts, so its bytes must not change to suit my index; the index
# learns its key instead. Which way the accommodation goes is the whole point: a published
# artefact is fixed, a derived index is not.
PARENT_KEYS = ("corrects", "applies_to", "extends", "supersedes", "amends", "of_digest")
ADDENDUM_MARKS = ("addendum", "addendum_n", "kind")

def build(root="."):
    fwd, orphans, missing_parent, external_parent = {}, [], [], []
    for p in sorted(glob.glob(os.path.join(root, "receipts/*.json"))
                    + glob.glob(os.path.join(root, "chronicle/*.json"))
                    + glob.glob(os.path.join(root, "witness/*.json"))):
        rel = os.path.relpath(p, root)
        try: d = json.load(open(p, encoding="utf-8"))
        except Exception: continue
        if not isinstance(d, dict): continue
        # a parent key may hold a STRING or an OBJECT carrying {"file": ...}. The published
        # chronicle addendum uses the object form; reading both is the index's job.
        par = None
        for k in PARENT_KEYS:
            v = d.get(k)
            if isinstance(v, str): par = v; break
            if isinstance(v, dict) and isinstance(v.get("file"), str): par = v["file"]; break
        looks_like_addendum = any(k in d for k in ADDENDUM_MARKS) or "addendum" in rel
        if par is None:
            if looks_like_addendum and "addendum" in rel: orphans.append(rel)
            continue
        # resolve a bare filename beside the addendum itself before calling it external —
        # "digest-011.json" inside chronicle/ means chronicle/digest-011.json, not a foreign object
        cand = None
        for c in (par, os.path.join(os.path.dirname(rel), par)):
            if c and os.path.exists(os.path.join(root, c)): cand = c.replace("\\", "/"); break
        if cand is None:
            # a parent may legitimately live OUTSIDE this tree (a board post, another holder).
            # That is not a dangling pointer and must not be reported as one.
            external = ("/" not in par) or par.startswith(("http", "board ", "the ", "seq "))
            (external_parent if external else missing_parent).append({"addendum": rel, "names": par})
            continue
        fwd.setdefault(cand, []).append(rel)
    return {"forward_index": fwd,
            "addenda_naming_a_parent_we_do_not_hold": missing_parent,
            "addenda_whose_parent_is_outside_this_tree": external_parent,
            "files_that_look_like_addenda_but_name_no_parent": orphans,
            "read_me": "open any file listed as a key here TOGETHER WITH the files listed under it; "
                       "the key was corrected or extended by them and does not say so itself",
            "counts": {"corrected_files": len(fwd),
                       "corrections": sum(len(v) for v in fwd.values())},
            "verdict": ("NOTHING INDEXED — no file in this tree names a parent"
                        if not fwd else "%d corrected files, %d corrections"
                        % (len(fwd), sum(len(v) for v in fwd.values())))}

def selftest():
    import tempfile
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "receipts"))
    def w(n, o): json.dump(o, open(os.path.join(d, "receipts", n), "w"))
    w("a.json", {"subject": "parent"})
    w("a-addendum-001.json", {"corrects": "receipts/a.json", "addendum_n": 1})
    w("b-addendum-001.json", {"applies_to": "receipts/a.json"})
    w("c-addendum-001.json", {"corrects": "receipts/gone.json"})
    w("d-addendum-001.json", {"note": "names nobody"})
    w("e-addendum-001.json", {"of_digest": {"file": "receipts/a.json", "digest_n": 1}})
    w("f-addendum-001.json", {"corrects": "a.json"})   # bare name, beside the addendum
    r = build(d)
    cases = [("a parent is indexed by every key that can name it, string OR nested object",
              sorted(x.split('/')[-1] for x in r["forward_index"]["receipts/a.json"])
              == ["a-addendum-001.json", "b-addendum-001.json", "e-addendum-001.json",
                  "f-addendum-001.json"], r["forward_index"]),
             ("a bare filename resolves beside the addendum, not to 'outside the tree'",
              "receipts/f-addendum-001.json" in r["forward_index"]["receipts/a.json"], r["forward_index"]),
             ("must catch: an addendum naming a parent we do not hold is reported, not dropped",
              len(r["addenda_naming_a_parent_we_do_not_hold"]) == 1, r["addenda_naming_a_parent_we_do_not_hold"]),
             ("must catch: a file shaped like an addendum that names nobody is an ORPHAN",
              r["files_that_look_like_addenda_but_name_no_parent"] == ["receipts/d-addendum-001.json"],
              r["files_that_look_like_addenda_but_name_no_parent"]),
             ("an empty tree says NOTHING INDEXED rather than passing silently",
              build(tempfile.mkdtemp())["verdict"].startswith("NOTHING INDEXED"), None)]
    bad = 0
    for label, ok, info in cases:
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok: bad += 1; print("        " + json.dumps(info, ensure_ascii=False)[:200])
    print("selftest: %d/%d" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0

if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]: sys.exit(selftest())
    print(json.dumps(build(sys.argv[1] if sys.argv[1:] else "."), ensure_ascii=False, indent=1))
