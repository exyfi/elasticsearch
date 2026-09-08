import sys,json,urllib.request,urllib.error,time
def probe(seq):
    u="https://agent-board.sobieg.ru/md/%d"%seq
    r=urllib.request.Request(u,headers={"User-Agent":"gpb-reader/1.0","Accept":"*/*"})
    try:
        h=urllib.request.urlopen(r,timeout=30); b=h.read()
        hd={k.lower():v for k,v in h.headers.items()}
        return {"seq":seq,"http":h.status,"bytes":len(b),
                "x_post_status":hd.get("x-post-status"),"x_post_id":hd.get("x-post-id"),
                "x_post_author":hd.get("x-post-author"),"x_deletion_noticed":hd.get("x-deletion-noticed")}
    except urllib.error.HTTPError as e:
        hd={k.lower():v for k,v in e.headers.items()}
        return {"seq":seq,"http":e.code,"bytes":len(e.read()),
                "x_post_status":hd.get("x-post-status"),"x_post_id":hd.get("x-post-id"),
                "x_post_author":hd.get("x-post-author"),"x_deletion_noticed":hd.get("x-deletion-noticed")}
    except Exception as ex:
        return {"seq":seq,"http":None,"error":str(ex)[:80]}
groups={
 "CONTROL alive (in my corpus, live on board)":[16408,19500,21575,22600-1,23900],
 "CONTROL deleted (proven: body in coolthings, 404 on board)":[21880,21888,21894,21902,24191],
 "THE ELEVEN unresolved":[19604,19796,19799,19922,20573,21573,22394,22899,23030,23034,23037],
}
out={}
for g,ss in groups.items():
    print("==",g)
    rows=[]
    for s in ss:
        r=probe(s); rows.append(r)
        print("  %6d  HTTP %-4s %6s B  status=%-42s author=%s"%(
            s,r.get("http"),r.get("bytes"),str(r.get("x_post_status"))[:42],r.get("x_post_author")))
        time.sleep(0.15)
    out[g]=rows
json.dump(out,open("sobieg-probe.json","w"),ensure_ascii=False,indent=1)
