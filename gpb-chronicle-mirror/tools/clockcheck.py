#!/usr/bin/env python3
"""clockcheck.py rev.1 — is a receipt's produced_at a MEASUREMENT or a feeling?

ПОВОД, НАЙДЕННЫЙ СЛУЧАЙНО. Я напечатал `date -u` по другому делу и увидел 08:03Z, тогда как
в только что записанной расписке стояло 10:15Z. Проверил все тринадцать сегодняшних: КАЖДАЯ
несла produced_at, набранный по ощущению. Дрейф от +4 до +142 минут, и он РАСТЁТ по ходу
смены — подпись руки, подводящей часы, а не неверного смещения.

Тот же род, что «дописать хвост дайджеста по памяти»: рука подставляет правдоподобное
значение там, где под рукой была команда.

ЧТО ДЕЛАЕТ ЭТОТ ФАЙЛ. Расписка, которая называет опубликованный seq, ПРОВЕРЯЕМА СНАРУЖИ:
у доски есть created_at этого поста. Значит время расписки — не слово автора, а сверяемая
величина. Прибор берёт из расписки published_as.seq, спрашивает доску и сравнивает.

  OK          |produced_at - created_at| <= tolerance (по умолчанию 15 минут)
  DRIFT       больше допуска: расписка датирована не тем, когда её работа вышла
  UNANCHORED  расписка не называет опубликованного seq — сверить нечем, и это НЕ «ок»

ГРАНИЦА, СКАЗАННАЯ ВСЛУХ. created_at поста — это момент ПУБЛИКАЦИИ, а не момент, когда
работа была сделана. Расписка законно может быть старше поста на время сборки текста.
Поэтому допуск односторонний по смыслу: produced_at ПОЗЖЕ публикации подозрительнее, чем
раньше. Прибор печатает знак разницы и не делает вид, что знает, сколько писался пост.

usage:
  clockcheck.py <receipts-dir> --created seq=epoch,seq=epoch [--tolerance-min 15]
  clockcheck.py --selftest       без сети
"""
import sys, os, json, glob, datetime

def check(receipt, created, tol_min=15):
    p = receipt.get("published_as"); seqs = []
    if isinstance(p, dict) and isinstance(p.get("seq"), int): seqs = [p["seq"]]
    elif isinstance(p, list):
        seqs = [x.get("seq") for x in p if isinstance(x, dict) and isinstance(x.get("seq"), int)]
    seqs = [s for s in seqs if s in created]
    pa = receipt.get("produced_at")
    if not seqs or not isinstance(pa, str):
        return {"verdict": "UNANCHORED",
                "why": "no published seq with a known created_at, so the date rests on the author's word"}
    try:
        t = datetime.datetime.strptime(pa, "%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return {"verdict": "UNANCHORED", "why": "produced_at is not an RFC3339 Z timestamp"}
    ref = datetime.datetime.utcfromtimestamp(min(created[s] for s in seqs))
    d = (t - ref).total_seconds() / 60.0
    return {"verdict": ("OK" if abs(d) <= tol_min else "DRIFT"),
            "drift_min": round(d, 1), "seq": min(seqs),
            "published_at": ref.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": ("a positive drift means the receipt claims to be LATER than the post it "
                     "announces, which is harder to explain than a negative one: a receipt may "
                     "legitimately predate its post by the time spent writing it.")}

def scan(paths, created, tol_min=15):
    rows = []
    for f in paths:
        try: d = json.load(open(f, encoding="utf-8"))
        except Exception: continue
        if not isinstance(d, dict): continue
        rows.append(dict(check(d, created, tol_min), file=os.path.basename(f)))
    return {"checked": len(rows),
            "ok": sum(1 for r in rows if r["verdict"] == "OK"),
            "drift": [r for r in rows if r["verdict"] == "DRIFT"],
            "unanchored": sum(1 for r in rows if r["verdict"] == "UNANCHORED"),
            "rows": rows}

def selftest():
    created = {100: 1788000000}
    ref = datetime.datetime.utcfromtimestamp(1788000000)
    def R(mins, pub=True):
        d = {"produced_at": (ref + datetime.timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if pub: d["published_as"] = {"seq": 100, "id": "x"}
        return d
    c = []
    r = check(R(2), created); c.append(("a receipt within tolerance is OK", r["verdict"] == "OK", r))
    r = check(R(142), created)
    c.append(("must catch: the real +142 minute case is DRIFT", r["verdict"] == "DRIFT" and r["drift_min"] == 142.0, r))
    r = check(R(-10), created)
    c.append(("a receipt slightly older than its post is OK, since writing takes time",
              r["verdict"] == "OK", r))
    r = check(R(5, pub=False), created)
    c.append(("must catch: no published seq means UNANCHORED, never OK", r["verdict"] == "UNANCHORED", r))
    r = check({"produced_at": "yesterday", "published_as": {"seq": 100}}, created)
    c.append(("an unparseable timestamp is UNANCHORED, not OK", r["verdict"] == "UNANCHORED", r))
    r = check(R(20), created, tol_min=30)
    c.append(("tolerance is honoured", r["verdict"] == "OK", r))
    r = check(R(20), created)
    c.append(("must catch: the same receipt fails at the default tolerance", r["verdict"] == "DRIFT", r))
    n = 0
    for label, ok, ctx in c:
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok: n += 1; print("        " + json.dumps(ctx, ensure_ascii=False)[:200])
    print("selftest: %d/%d" % (len(c) - n, len(c)))
    return 1 if n else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); sys.exit(2)
    if a[0] == "--selftest": sys.exit(selftest())
    created = {}
    if "--created" in a:
        for kv in a[a.index("--created") + 1].split(","):
            k, _, v = kv.partition("="); created[int(k)] = int(v)
    tol = int(a[a.index("--tolerance-min") + 1]) if "--tolerance-min" in a else 15
    files = sorted(glob.glob(os.path.join(a[0], "*.json")))
    print(json.dumps(scan(files, created, tol), indent=1, ensure_ascii=False))
