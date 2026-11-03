"""Descarga el mapa significativo de baja cota de AEMET AMA a data/swc.png.
Usa los secretos AMA_USER y AMA_PASS. No imprime credenciales."""
import os, re, sys, pathlib, html
from urllib.parse import urljoin
import requests

BASE = "https://ama.aemet.es/"
MAP_URL = BASE + "mapas-aeronauticos?p_p_id=busquedasbasicas&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_busquedasbasicas_idConsulta=39802"
USER, PASS = os.environ.get("AMA_USER", ""), os.environ.get("AMA_PASS", "")
DEBUG = os.environ.get("AMA_DEBUG") == "1"
s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def log(*a):
    print(*a, flush=True)

def forms(page):
    out = []
    for m in re.finditer(r"<form\b([^>]*)>(.*?)</form>", page, re.S | re.I):
        attrs, body = m.group(1), m.group(2)
        action = html.unescape((re.search(r'action="([^"]*)"', attrs) or [None, ""])[1])
        inputs = []
        for i in re.finditer(r"<input\b([^>]*)>", body, re.I):
            ia = i.group(1)
            name = (re.search(r'name="([^"]*)"', ia) or [None, None])[1]
            typ = ((re.search(r'type="([^"]*)"', ia) or [None, "text"])[1]).lower()
            val = html.unescape((re.search(r'value="([^"]*)"', ia) or [None, ""])[1])
            if name:
                inputs.append((name, typ, val))
        out.append((action, inputs))
    return out

def show(tag, r):
    log(f"[{tag}] {r.status_code} {r.url}")
    if DEBUG:
        t = r.text
        log("  title:", (re.search(r"<title>(.*?)</title>", t, re.S | re.I) or [None, "-"])[1].strip()[:120])
        for a, ins in forms(t):
            log("  form ->", a[:160], [(n, ty) for n, ty, _ in ins])
        log("  logout en página:", bool(re.search(r"logout|cerrar sesi", t, re.I)))

if not USER or not PASS:
    log("Faltan los secretos AMA_USER / AMA_PASS"); sys.exit(0)

r = s.get(BASE, timeout=30); show("inicio", r)
page, url = r.text, r.url
login_form = next(((a, i) for a, i in forms(page) if any(t == "password" for _, t, _ in i)), None)
if not login_form:
    # buscar enlace de acceso
    m = re.search(r'href="([^"]*(?:login|acceder|iniciar)[^"]*)"', page, re.I)
    if m:
        r = s.get(urljoin(url, html.unescape(m.group(1))), timeout=30); show("login", r)
        page, url = r.text, r.url
        login_form = next(((a, i) for a, i in forms(page) if any(t == "password" for _, t, _ in i)), None)
if not login_form:
    log("No encuentro el formulario de acceso"); sys.exit(0)

action, inputs = login_form
data = {}
for name, typ, val in inputs:
    if typ == "password":
        data[name] = PASS
    elif typ in ("text", "email") and re.search(r"login|user|usuario|email", name, re.I):
        data[name] = USER
    elif typ in ("hidden", "checkbox") or val:
        data[name] = val
r = s.post(urljoin(url, action), data=data, timeout=30); show("tras login", r)
if re.search(r'type="password"', r.text) and not re.search(r"logout|cerrar sesi", r.text, re.I):
    log("El acceso parece haber fallado (sigue el formulario de contraseña)")

r = s.get(MAP_URL, timeout=30); show("mapa", r)
t = r.text
cands = []
for m in re.finditer(r'<img\b[^>]*src="([^"]+)"', t, re.I):
    src = html.unescape(m.group(1))
    if re.search(r"logo|icon|sprite|spacer|banner|\.svg", src, re.I):
        continue
    cands.append(urljoin(r.url, src))
for m in re.finditer(r'(?:href|data-src|src)="([^"]*(?:serveResource|p_p_lifecycle=2|/documents/|\.png|\.gif|\.jpe?g)[^"]*)"', t, re.I):
    u = urljoin(r.url, html.unescape(m.group(1)))
    if u not in cands and not re.search(r"logo|icon|favicon|\.css|\.js", u, re.I):
        cands.append(u)
log("Candidatos de imagen:", len(cands))
for u in cands[:15]:
    log("  ", re.sub(r"(p_auth|token|auth)=[^&]+", r"\1=***", u)[:200])

best = None
for u in cands:
    try:
        ir = s.get(u, timeout=30)
    except Exception as e:
        continue
    ct = ir.headers.get("content-type", "")
    if ct.startswith("image/") and len(ir.content) > 30000:
        if not best or len(ir.content) > len(best[1]):
            best = (u, ir.content, ct)
if best:
    pathlib.Path("data").mkdir(exist_ok=True)
    ext = "png"
    pathlib.Path("data/swc.png").write_bytes(best[1])
    log(f"Mapa guardado: {len(best[1])} bytes, {best[2]}")
else:
    log("No he encontrado una imagen de mapa")
