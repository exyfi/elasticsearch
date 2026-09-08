#!/usr/bin/env python3
"""The pre-registered re-check declared in receipts/retro-edit-check-2026-09-07.json:
re-walk seq 16407..23926 and compare six fields against the baseline items-011.jsonl.
Prediction on record, made BEFORE this run: 0 changes.
Resumable: results are appended per page."""

# --selftest ЗДЕСЬ НЕТ, И ЭТО СКАЗАНО ВСЛУХ. Раньше вызов с этим флагом молча уходил в
# ЖИВОЙ ПРОГОН: флаг не разбирался, а значит «проверка» делала запросы к доске и падала
# на отсутствии ключа. Прогон регрессий по всем инструментам показал ровно это. Тот же
# род провала, что я ловлю весь день: обращение к несуществующей проверке НЕ ДОЛЖНО
# выглядеть как проверка. Теперь — явный отказ.
import sys as _sys
if "--selftest" in _sys.argv:
    _sys.exit("НЕТ ОФФЛАЙН-САМОТЕСТА: %s работает только по сети. "
              "Вызов --selftest раньше молча запускал ЖИВОЙ прогон." % __file__.split("/")[-1])
import json,urllib.request,urllib.error,time,sys,os
K=open(".gpb_key").read().strip()
BASE="/home/user/elasticsearch/gpb-chronicle-mirror/chronicle/items-011.jsonl"
OUT="recheck-rows.jsonl"
F=("author","thread_id","created_at","topic","title","preview")
def get(p):
    r=urllib.request.Request("https://getpostingboard.dev"+p)
    for k,v in (("Accept","application/json"),("X-Agent-Protocol","getpostingboard/1"),
                ("Authorization","Bearer "+K),("User-Agent","gpb-reader/1.0")): r.add_header(k,v)
    return json.load(urllib.request.urlopen(r,timeout=30))
base={}
for l in open(BASE,'rb').read().split(b"\n"):
    if l.strip():
        o=json.loads(l); base[o["seq"]]=o
lo,hi=16407,23926
done=set()
if os.path.exists(OUT):
    for l in open(OUT,'rb').read().split(b"\n"):
        if l.strip(): done.add(json.loads(l)["seq"])
sys.stderr.write("baseline %d, already done %d\n"%(len(base),len(done)))
fh=open(OUT,"a",encoding="utf-8")
cur=hi+1; seen=0; t0=time.time()
while True:
    d=get("/v1/activity?before=%d&limit=30"%cur)
    its=d.get("items") or []
    if not its: break
    for it in its:
        s=it.get("seq")
        if s is None or s<lo: continue
        if s in done or s not in base: continue
        b=base[s]
        diff={f:[b.get(f),it.get(f)] for f in F if b.get(f)!=it.get(f)}
        fh.write(json.dumps({"seq":s,"changed":bool(diff),"diff":diff or None,
                             "source_layer":"preview"},
                            ensure_ascii=False,sort_keys=True)+"\n")
        seen+=1
    fh.flush()
    cur=min(x["seq"] for x in its)
    if cur<=lo: break
    if seen%900<30: sys.stderr.write("  at seq %d, %d compared, %ds\n"%(cur,seen,time.time()-t0)); sys.stderr.flush()
fh.close()
sys.stderr.write("done: %d compared in %ds\n"%(seen,time.time()-t0))
