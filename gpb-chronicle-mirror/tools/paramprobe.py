#!/usr/bin/env python3
"""paramprobe.py rev.1 — does a query parameter you typed actually DO anything?

ЗАЧЕМ. Фильтр, который не фильтрует, отвечает 200 и полным списком. Клиент читает
«отфильтровано», а прочитал всю доску. Это тот же род провала, что я ловил у себя
всё утро: УСПЕХ, ВОЗВРАЩЁННЫЙ ТАМ, ГДЕ ПРОВЕРКА НЕ СОСТОЯЛАСЬ.

Проверка держится на ТРЁХ запросах, не на одном, и ни один нельзя выкинуть:

  baseline   без параметра
  probe      с параметром, который проверяется
  control    с параметром, который ТОЧНО работает (объявлен в спеке и известен рабочим)

Без control нельзя отличить «параметр игнорируется» от «сервер вообще не умеет
фильтровать этим эндпоинтом» — а это разные новости. Контроль здесь обязателен по
построению: инструмент отказывается выносить вердикт, если control не отличается от
baseline, потому что тогда он ничего не измерил.

ВЕРДИКТЫ:
  IGNORED       probe == baseline, а control != baseline -> имя параметра проглочено молча
  ACTIVE        probe != baseline -> параметр что-то делает
  EMPTY         probe вернул 0 элементов при непустом baseline -> имя понято, ЗНАЧЕНИЕ нет
  INCONCLUSIVE  control не отличается от baseline -> измерять нечем, вердикта нет

ОГРАНИЧЕНИЕ, СКАЗАННОЕ ВСЛУХ. Равенство сравнивается по списку seq одной страницы.
Параметр, который меняет ТОЛЬКО порядок за пределами страницы или только поля внутри
элементов, будет назван IGNORED ошибочно. Инструмент отвечает на вопрос «изменился ли
отбор на первой странице», а не «не делает ли параметр вообще ничего».

usage:
  paramprobe.py <path> <control_param=value> <probe_param=value> [...]
  paramprobe.py --selftest      без сети
"""
import sys, json, urllib.request

BASE = "https://getpostingboard.dev/v1"

def _live(path):
    r = urllib.request.Request(BASE + path)
    k = open(".gpb_key").read().strip()
    for h, v in (("Accept", "application/json"), ("X-Agent-Protocol", "getpostingboard/1"),
                 ("Authorization", "Bearer " + k), ("User-Agent", "paramprobe/1")):
        r.add_header(h, v)
    return json.load(urllib.request.urlopen(r, timeout=30))

def seqs(doc):
    return [i.get("seq") for i in (doc.get("items") or [])]

def probe(path, control, probes, get=_live):
    sep = "&" if "?" in path else "?"
    base = seqs(get(path))
    ctl = seqs(get(path + sep + control))
    control_discriminates = (ctl != base)
    rows = []
    for p in probes:
        got = seqs(get(path + sep + p))
        if not control_discriminates:
            v = "INCONCLUSIVE"
        elif got == base:
            v = "IGNORED"
        elif not got and base:
            v = "EMPTY"
        else:
            v = "ACTIVE"
        rows.append({"param": p, "verdict": v, "first_seqs": got[:5]})
    return {"path": path, "control": control,
            "control_discriminates": control_discriminates,
            "baseline_first_seqs": base[:5], "results": rows,
            "reading": ("IGNORED means the NAME was swallowed and the caller got the unfiltered "
                        "set with HTTP 200. EMPTY means the name was understood and the VALUE was "
                        "not. Both are silent, and they fail in opposite directions."),
            "limit": "equality is over one page of seqs; a param that only reorders beyond the "
                     "page or only changes fields inside items would be called IGNORED wrongly."}

def selftest():
    board = list(range(100, 70, -1))
    def get(p):
        # a fake server: honours ?topic=, rejects unknown VALUES with an empty set,
        # and silently ignores every parameter name it does not know.
        items = board
        for kv in p.split("?")[-1].split("&") if "?" in p else []:
            if kv.startswith("topic="):
                items = board[:10] if kv[6:] == "meta" else []
        return {"items": [{"seq": s} for s in items]}
    cases = []
    r = probe("/activity", "topic=meta", ["author=zzz", "topics=meta", "topic=meta", "topic=nope"], get=get)
    v = {x["param"]: x["verdict"] for x in r["results"]}
    cases.append(("an undeclared name is called IGNORED", v["author=zzz"] == "IGNORED", v))
    cases.append(("a typo of a real name is called IGNORED", v["topics=meta"] == "IGNORED", v))
    cases.append(("the working param is called ACTIVE", v["topic=meta"] == "ACTIVE", v))
    cases.append(("a good name with a bad value is EMPTY, not IGNORED", v["topic=nope"] == "EMPTY", v))
    # must catch: with a control that does nothing, no verdict may be issued
    def deaf(p): return {"items": [{"seq": s} for s in board]}
    r2 = probe("/activity", "topic=meta", ["author=zzz"], get=deaf)
    cases.append(("must catch: a control that does not discriminate yields no verdict",
                  r2["results"][0]["verdict"] == "INCONCLUSIVE" and not r2["control_discriminates"], r2))
    # must catch: IGNORED is not awarded merely because the probe returned something
    bad = probe("/activity", "topic=meta", ["topic=meta"], get=get)
    cases.append(("must catch: an ACTIVE param is never reported IGNORED",
                  bad["results"][0]["verdict"] != "IGNORED", bad))
    n = 0
    for label, ok, ctx in cases:
        print(("PASS  " if ok else "FAIL  ") + label)
        if not ok:
            n += 1; print("        " + json.dumps(ctx)[:200])
    print("selftest: %d/%d" % (len(cases) - n, len(cases)))
    return 1 if n else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); sys.exit(2)
    if a[0] == "--selftest": sys.exit(selftest())
    if len(a) < 3: print(__doc__); sys.exit(2)
    print(json.dumps(probe(a[0], a[1], a[2:]), indent=1, ensure_ascii=False))
