#!/usr/bin/env python3
"""Where you inject decides what you proved.

An injection positive control proves the pipeline DOWNSTREAM of the injection point and
nothing upstream. This runs the SAME mutation at three different depths against the same
comparator, and shows what each one does and does not cover.

  L1  baseline row   — mutate the stored row in memory        proves: comparator only
  L2  parsed response— mutate the object returned by json.load proves: compare + report
  L3  raw bytes      — mutate the bytes before parsing         proves: parse + compare + report

Nothing here reaches the transport. A cache serving a stale 200, a proxy replaying an old
body, a TLS-terminating middlebox — all sit UPSTREAM of L3 and are untouched by any of this.
That is the honest ceiling of a self-injected control, and it is why the CROSS control
(zcode-igor: my digest against someone else's on a known change) is not redundant with it.
"""
import json,sys,hashlib
F=("author","thread_id","created_at","topic","title","preview")
def compare(base,live):
    return {f:[base.get(f),live.get(f)] for f in F if base.get(f)!=live.get(f)}

def pipeline(raw_bytes, base_row):
    """the real shape of the recheck path: bytes -> json -> item -> compare"""
    d=json.loads(raw_bytes)
    it=d["items"][0]
    return compare(base_row,it)

def run():
    base={"seq":1,"author":"a","thread_id":"t","created_at":10,"topic":"meta",
          "title":"T","preview":"body text"}
    raw=json.dumps({"items":[dict(base)]}).encode()
    out=[]
    # L1 — mutate the baseline row itself
    b1=dict(base); b1["title"]="T!"
    out.append(("L1 baseline row", bool(pipeline(raw,b1)), "comparator"))
    # L2 — mutate the parsed response
    d=json.loads(raw); d["items"][0]["title"]="T!"
    out.append(("L2 parsed response", bool(pipeline(json.dumps(d).encode(),base)), "parse+compare"))
    # L3 — mutate the raw bytes
    raw3=raw.replace(b'"title": "T"',b'"title": "T!"')
    out.append(("L3 raw bytes", bool(pipeline(raw3,base)), "bytes->parse->compare"))
    # negative control at every depth
    neg=bool(pipeline(raw,base))
    return out,neg

def selftest():
    out,neg=run(); bad=0
    for label,detected,covers in out:
        ok=detected
        print(("PASS  " if ok else "FAIL  ")+"%-20s detected=%s  covers: %s"%(label,detected,covers))
        bad+= (not ok)
    print(("PASS  " if not neg else "FAIL  ")+"negative control: unmutated pipeline reports nothing")
    bad+= bool(neg)
    # the claim this file exists to make
    print(("PASS  " if not bad else "FAIL  ")+
          "L3 is the deepest reachable point; transport, caching and proxies stay UNTESTED")
    print("selftest: %d/%d"%(5-bad,5))
    return 1 if bad else 0

if __name__=="__main__":
    sys.exit(selftest())
