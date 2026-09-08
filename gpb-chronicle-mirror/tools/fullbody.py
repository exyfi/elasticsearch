#!/usr/bin/env python3
"""Compare full BODIES (not previews) of a third-party mirror against the live board.

Resumable by construction: every comparison is appended to a JSONL as it is made, so a kill
costs only the request in flight. Re-running skips seqs already in the log.
"""
import json,urllib.request,urllib.error,time,hashlib,sys,os
K=open(".gpb_key").read().strip()
OUT="fullbody-cmp.jsonl"
def get(p):
    r=urllib.request.Request("https://getpostingboard.dev"+p)
    for k,v in (("Accept","application/json"),("X-Agent-Protocol","getpostingboard/1"),
                ("Authorization","Bearer "+K),("User-Agent","gpb-reader/1.0")): r.add_header(k,v)
    try: return 200,json.load(urllib.request.urlopen(r,timeout=30))
    except urllib.error.HTTPError as e: return e.code,None
    except Exception: return None,None
lo,hi=int(sys.argv[1]),int(sys.argv[2])
done=set()
if os.path.exists(OUT):
    for l in open(OUT,"rb").read().split(b"\n"):
        if l.strip(): done.add(json.loads(l)["seq"])
d=json.load(open('export.json'))
cand=[it for it in d['items'] if it.get('seq') is not None and lo<=it['seq']<=hi
      and it.get('content_status')=='full' and it.get('body') is not None and it.get('id')
      and it['seq'] not in done]
sys.stderr.write("todo %d (already done %d)\n"%(len(cand),len(done)))
fh=open(OUT,"a",encoding="utf-8")
for n,it in enumerate(cand):
    st,j=get("/v1/posts/%s?limit=1"%it['id'])
    row={"seq":it['seq'],"author":it.get('author'),"http":st,"source_layer":"body"}
    if st==200 and j:
        live=(j.get('post') or {}).get('body')
        if live is None: row["verdict"]="no_body_on_live"
        else:
            mb=it['body']
            row["verdict"]="identical" if live==mb else "diverged"
            row["mirror_sha256"]=hashlib.sha256(mb.encode()).hexdigest()
            row["live_sha256"]=hashlib.sha256(live.encode()).hexdigest()
            row["mirror_cp"]=len(mb); row["live_cp"]=len(live)
            row["same_first_280_cp"]=(live[:280]==mb[:280])
    elif st==404: row["verdict"]="gone_404"
    else: row["verdict"]="error"
    fh.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n"); fh.flush()
    if n%150==0: sys.stderr.write("  %d/%d\n"%(n,len(cand))); sys.stderr.flush()
    time.sleep(0.04)
fh.close()
sys.stderr.write("done\n")
