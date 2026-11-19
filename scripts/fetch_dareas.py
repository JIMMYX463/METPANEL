"""Zonas D (peligrosas) activadas por NOTAM en España peninsular, con su polígono.
Fuente: ENAIRE (servicio NOTAM de Insignia, capa «Áreas»). Escribe data/dareas.json."""
import json, time, pathlib, urllib.parse, urllib.request

URL = "https://servais.enaire.es/insignias/rest/services/NOTAM/NOTAM_APP_V3/FeatureServer/1/query"
OUT = pathlib.Path("data/dareas.json")
FIELDS = "notamId,affectedElement,qcode,fir,itemB,itemC,itemBstr,itemCstr,itemD,itemE,itemF,itemG,LOWER_VAL,UPPER_VAL,icaoFormatText"


def main():
    q = urllib.parse.urlencode({"where": "qcode='RDCA'", "outFields": FIELDS, "returnGeometry": "true",
                                "outSR": "4326", "geometryPrecision": "4", "f": "json"})
    req = urllib.request.Request(URL + "?" + q, headers={"User-Agent": "METPANEL (github.com/JIMMYX463/METPANEL)"})
    d = json.load(urllib.request.urlopen(req, timeout=90))
    if "features" not in d:
        print("ENAIRE sin datos:", str(d)[:300]); return
    now = time.time() * 1000
    areas = []
    for f in d["features"]:
        a, g = f["attributes"], f.get("geometry") or {}
        rings = [[[round(y, 4), round(x, 4)] for x, y in r] for r in g.get("rings", [])]
        if not rings:
            continue
        lats = [p[0] for r in rings for p in r]; lons = [p[1] for r in rings for p in r]
        # Solo península (fuera Canarias, Baleares y Ceuta/Melilla aparte del sur peninsular)
        if min(lats) < 35.5 or max(lons) > 3.4 or min(lons) < -10:
            continue
        b, c = a.get("itemB") or 0, a.get("itemC") or 0
        if c and c < now:            # ya caducado
            continue
        if b and b > now + 48 * 3600e3:  # empieza más allá de 48 h
            continue
        areas.append({
            "id": (a.get("affectedElement") or "").strip(), "notam": a.get("notamId"),
            "from": b, "to": c, "fromStr": a.get("itemBstr"), "toStr": a.get("itemCstr"),
            "sched": (a.get("itemD") or "").strip(), "lower": (a.get("itemF") or "").strip(),
            "upper": (a.get("itemG") or "").strip(), "text": (a.get("icaoFormatText") or a.get("itemE") or "").strip(),
            "rings": rings,
        })
    areas.sort(key=lambda x: (x["id"], x["from"]))
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    if old.get("areas") == areas:
        print("Sin cambios en las zonas D (%d)." % len(areas)); return
    OUT.write_text(json.dumps({"fetched": int(time.time()), "source": "ENAIRE NOTAM", "areas": areas},
                              ensure_ascii=False, separators=(",", ":")))
    print("Zonas D guardadas:", len(areas), sorted(set(x["id"] for x in areas)))


if __name__ == "__main__":
    main()
