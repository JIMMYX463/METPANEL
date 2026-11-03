"""Descarga los NOTAM de los aeródromos del panel desde la búsqueda pública de NOTAM de la FAA
y los guarda en data/notam.json (formato {"notamList": [...], "fetched": epoch})."""
import json, pathlib, re, sys, time
from curl_cffi import requests as cr

html = pathlib.Path("index.html").read_text()
groups = html[html.index("const GROUPS="):html.index("const AIRPORTS=")]
IDS = sorted(set(re.findall(r'\b([A-Z]{4}):"', groups)))
URL = "https://notams.aim.faa.gov/notamSearch/search"
REF = "https://notams.aim.faa.gov/notamSearch/nsapp.html"

s = cr.Session(impersonate="chrome")
s.get(REF, timeout=30)
out, failed = {}, []
for i in range(0, len(IDS), 6):
    batch = IDS[i:i + 6]
    offset, total = 0, None
    while total is None or offset < total:
        try:
            r = s.post(URL, timeout=40, headers={"Referer": REF, "X-Requested-With": "XMLHttpRequest"},
                       data={"searchType": "0", "designatorsForLocation": ",".join(batch),
                             "offset": str(offset), "notamsOnly": "false"})
            j = r.json()
        except Exception as e:
            print("Error en", batch, offset, repr(e)[:150]); failed += batch; break
        lst = j.get("notamList") or []
        total = int(j.get("totalNotamCount") or len(lst))
        for n in lst:
            key = (n.get("facilityDesignator"), n.get("notamNumber"))
            out[key] = {k: n.get(k) for k in ("facilityDesignator", "icaoId", "notamNumber", "issueDate",
                                              "startDate", "endDate", "icaoMessage", "traditionalMessageFrom4thWord")}
        if not lst:
            break
        offset += len(lst)
        time.sleep(1)
    time.sleep(1)

print(f"{len(out)} NOTAM de {len(IDS)} aeródromos · fallos: {sorted(set(failed))}")
if not out:
    sys.exit(0)  # no sobrescribir el archivo anterior si no llega nada
pathlib.Path("data").mkdir(exist_ok=True)
pathlib.Path("data/notam.json").write_text(json.dumps({"fetched": int(time.time()), "notamList": list(out.values())}, ensure_ascii=False))
