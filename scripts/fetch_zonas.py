"""Zonas D, P, R y TSA/TRA de España peninsular activas por NOTAM o por AIP, con su polígono (ENAIRE).
- NOTAM: servicio NOTAM de Insignia (capa «Áreas», con la geometría ya calculada).
- AIP: espacio aéreo en vigor (capa D_P_R), zonas activas H24, HJ o con horario en observaciones.
Escribe data/zonas_notam.json y data/zonas_aip.json (este casi nunca cambia)."""
import json, re, time, pathlib, urllib.parse, urllib.request

UA = {"User-Agent": "METPANEL (github.com/JIMMYX463/METPANEL)"}
NOTAM = "https://servais.enaire.es/insignias/rest/services/NOTAM/NOTAM_APP_V3/FeatureServer/1/query"
AIP = "https://servais.enaire.es/insignias/rest/services/INSIGNIA_VIGOR/Aero_APP_VIGOR_Airspace_V_6/MapServer/{}/query"


def get(url, **p):
    p.setdefault("f", "json")
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(p), headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=120))


def rings_of(g):
    return [[[round(y, 4), round(x, 4)] for x, y in r] for r in (g or {}).get("rings", [])]


def peninsula(rings):
    lats = [p[0] for r in rings for p in r]; lons = [p[1] for r in rings for p in r]
    return rings and min(lats) > 35.6 and max(lats) < 44.5 and min(lons) > -10 and max(lons) < 3.5


def kind_notam(q, el, text):
    el = (el or "").upper(); t = (text or "").upper()
    if el.startswith("LETS") or el.startswith("LETR") or re.search(r"\bTSA\b|\bTRA\b", t):
        return "TSA"
    if q == "RDCA" or el.startswith("LED"):
        return "D"
    if el.startswith("LEP"):
        return "P"
    return "R"


def notams(now):
    d = get(NOTAM, where="qcode IN ('RDCA','RRCA','RTCA','RACA','RPCA')", returnGeometry="true", outSR="4326",
            geometryPrecision="4", outFields="notamId,affectedElement,qcode,itemB,itemC,itemD,itemE,itemF,itemG,icaoFormatText")
    out = []
    for f in d.get("features", []):
        a = f["attributes"]; rings = rings_of(f.get("geometry"))
        if not peninsula(rings):
            continue
        b, c = a.get("itemB") or 0, a.get("itemC") or 0
        if (c and c < now) or (b and b > now + 48 * 3600e3):
            continue
        el = (a.get("affectedElement") or "").strip()
        ident = el if not el.startswith("DINV") else ""
        out.append({"t": kind_notam(a.get("qcode"), el, a.get("itemE")), "src": "NOTAM", "id": ident or "Temporal",
                    "notam": a.get("notamId"), "from": b, "to": c, "sched": (a.get("itemD") or "").strip(),
                    "lower": (a.get("itemF") or "").strip(), "upper": (a.get("itemG") or "").strip(),
                    "text": (a.get("icaoFormatText") or a.get("itemE") or "").strip(), "rings": rings})
    return out


def aip():
    rmk = {}
    try:  # horario en observaciones (capa de textos)
        for f in get(AIP.format(24), where="1=1", returnGeometry="false", outFields="GFID,WORKHRRMK_TXT").get("features", []):
            a = f["attributes"]
            if a.get("WORKHRRMK_TXT"):
                rmk[a["GFID"]] = a["WORKHRRMK_TXT"].strip()
    except Exception as e:
        print("AIP observaciones:", repr(e)[:150])
    d = get(AIP.format(4), where="WORKHR_CODE <> 'NOTAM'", returnGeometry="true", outSR="4326", geometryPrecision="4",
            maxAllowableOffset="0.002", outFields="GFID,IDENT_TXT,NAME_TXT,TYPE_CODE,WORKHR_CODE,NIVELES")
    out = []
    for f in d.get("features", []):
        a = f["attributes"]; rings = rings_of(f.get("geometry"))
        t = {"TRA": "TSA"}.get(a.get("TYPE_CODE"), a.get("TYPE_CODE"))
        if t not in ("D", "P", "R", "TSA") or not peninsula(rings):
            continue
        niv = [x.strip() for x in (a.get("NIVELES") or "").split("________")]
        upper, lower = (niv + ["", ""])[:2]
        wh = a.get("WORKHR_CODE") or ""
        sched = {"H24": "H24", "HJ": "HJ (de orto a ocaso)"}.get(wh, rmk.get(a.get("GFID"), "Según AIP (observaciones)"))
        out.append({"t": t, "src": "AIP", "id": (a.get("IDENT_TXT") or "").strip(), "name": (a.get("NAME_TXT") or "").strip(),
                    "sched": sched, "lower": lower, "upper": upper, "rings": rings})
    return out


def save(path, zs):
    path = pathlib.Path(path)
    old = json.loads(path.read_text()) if path.exists() else {}
    if old.get("zonas") == zs:
        print(path.name, "sin cambios (%d)" % len(zs)); return
    path.write_text(json.dumps({"fetched": int(time.time()), "source": "ENAIRE", "zonas": zs}, ensure_ascii=False, separators=(",", ":")))
    import collections
    print(path.name, len(zs), dict(collections.Counter(z["t"] for z in zs)), "· %d KB" % (path.stat().st_size // 1024))


def main():
    now = time.time() * 1000
    for name, fn in (("data/zonas_notam.json", lambda: notams(now)), ("data/zonas_aip.json", aip)):
        try:
            zs = fn()
        except Exception as e:
            print(name, "falló:", repr(e)[:200]); continue
        zs.sort(key=lambda z: (z["t"], z["id"], z.get("from", 0)))
        save(name, zs)


if __name__ == "__main__":
    main()
