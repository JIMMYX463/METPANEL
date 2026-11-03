import re, html, sys
from curl_cffi import requests as cr
IDS = ["LEBZ", "LEMO", "LPBJ"]
def show(name, r):
    t = r.text if r is not None else ""
    ids = sorted(set(re.findall(r"\b[A-Z]\d{4}/\d{2}\b", t)))
    print(f"=== {name}: HTTP {getattr(r,'status_code','-')} · {len(t)} bytes · NOTAM ids: {len(ids)} {ids[:6]}")
    txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", t, flags=re.S)))
    i = txt.find(ids[0]) if ids else -1
    print("   ", (txt[max(0, i-80):i+400] if i >= 0 else txt[:300]))
def get(name, url, **kw):
    try:
        r = cr.request(kw.pop("method", "GET"), url, impersonate="chrome", timeout=30, **kw); show(name, r)
    except Exception as e:
        print(f"=== {name}: ERROR {e!r}"[:300])
s = cr.Session(impersonate="chrome")
try:
    s.get("https://notams.aim.faa.gov/notamSearch/nsapp.html", timeout=30)
    r = s.post("https://notams.aim.faa.gov/notamSearch/search", timeout=30,
        headers={"Referer": "https://notams.aim.faa.gov/notamSearch/nsapp.html", "X-Requested-With": "XMLHttpRequest"},
        data={"searchType": "0", "designatorsForLocation": ",".join(IDS), "offset": "0", "notamsOnly": "false"})
    show("FAA NOTAM Search (curl_cffi)", r)
except Exception as e:
    print("=== FAA NOTAM Search: ERROR", repr(e)[:300])
get("FAA PilotWeb", "https://pilotweb.nas.faa.gov/PilotWeb/notamRetrievalByICAOAction.do?method=displayByICAOs&reportType=RAW&formatType=ICAO&retrieveLocId=LEBZ+LEMO+LPBJ&actionType=notamRetrievalByICAOs")
get("FAA DINS", "https://www.notams.faa.gov/dinsQueryWeb/queryRetrievalMapAction.do?reportType=Raw&retrieveLocId=LEBZ+LEMO+LPBJ&actionType=notamRetrievalByICAOs&submit=View+NOTAMs")
get("metarcentral", "https://metarcentral.com/airport/LEBZ/notam")
get("metar-taf.com", "https://metar-taf.com/notam/LEBZ")
get("acukwik", "https://acukwik.com/NOTAMs/LEBZ")
get("ENAIRE ICARO", "https://notampib.enaire.es/")
get("NAV Portugal ops", "https://ops.nav.pt/")
get("ourairports LEBZ", "https://ourairports.com/airports/LEBZ/notams.html")
