"""Mapa significativo de baja cota desde @meteolemobot (Telegram).
Modos:
  login  -> pide un código a Telegram, lo espera como comentario en una issue y guarda la sesión cifrada.
  fetch  -> envía '/sig HH ibe' y '/colores' al bot y guarda las imágenes en data/.
Secretos: TG_API_ID, TG_API_HASH, TG_PHONE y, si tienes verificación en dos pasos, TG_2FA.
Nunca imprime credenciales ni la sesión."""
import asyncio, base64, hashlib, json, os, pathlib, re, subprocess, sys, time
from cryptography.fernet import Fernet
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

BOT = "meteolemobot"
HOURS = ["00", "06", "12", "18"]
SESSION_FILE = pathlib.Path("data/tg.session.enc")
API_ID = int(os.environ.get("TG_API_ID") or 0)
API_HASH = os.environ.get("TG_API_HASH", "")
PHONE = os.environ.get("TG_PHONE", "")
PW = os.environ.get("TG_2FA", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")


def log(*a):
    print(*a, flush=True)


def fernet():
    key = hashlib.sha256(f"{API_ID}|{API_HASH}|{PHONE}|metpanel".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True)


async def login():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    sent = await client.send_code_request(PHONE)
    r = gh("issue", "create", "-R", REPO, "--title", "Código de Telegram",
           "--body", "Escribe aquí como comentario SOLO el código de 5 cifras que te ha llegado a Telegram. "
                     "Se borrará en cuanto se use.")
    url = r.stdout.strip()
    num = url.rsplit("/", 1)[-1]
    log("Issue para el código:", url or r.stderr.strip())
    code, cid = None, None
    end = time.time() + 600
    while time.time() < end and not code:
        time.sleep(5)
        c = gh("api", f"repos/{REPO}/issues/{num}/comments")
        try:
            for com in json.loads(c.stdout or "[]"):
                m = re.search(r"\b(\d{5,6})\b", com.get("body", ""))
                if m:
                    code, cid = m.group(1), com["id"]
                    break
        except Exception:
            pass
    if cid:
        gh("api", "-X", "DELETE", f"repos/{REPO}/issues/comments/{cid}")
    gh("issue", "close", num, "-R", REPO)
    if not code:
        log("No llegó ningún código en 10 minutos.")
        sys.exit(1)
    try:
        await client.sign_in(PHONE, code, phone_code_hash=sent.phone_code_hash)
    except SessionPasswordNeededError:
        if not PW:
            log("Tu cuenta tiene verificación en dos pasos: crea el secreto TG_2FA y repite el login.")
            sys.exit(1)
        await client.sign_in(password=PW)
    SESSION_FILE.parent.mkdir(exist_ok=True)
    SESSION_FILE.write_bytes(fernet().encrypt(client.session.save().encode()))
    log("Sesión de Telegram iniciada correctamente.")
    await client.disconnect()


async def ask(client, bot, cmd):
    """Envía un comando al bot y devuelve el primer mensaje con imagen de la respuesta."""
    sent = await client.send_message(bot, cmd)
    reply = ""
    for _ in range(20):
        await asyncio.sleep(2)
        async for m in client.iter_messages(bot, min_id=sent.id, limit=10):
            if m.out:
                continue
            reply = reply or (m.message or "")
            mime = (m.file.mime_type or "") if m.file else ""
            if m.photo or mime.startswith("image/"):
                await asyncio.sleep(3)
                return m
    log(f"{cmd}: sin imagen. Respuesta del bot: {reply[:200]!r}")
    return None


async def fetch():
    if not SESSION_FILE.exists():
        log("No hay sesión: lanza primero el modo login.")
        return
    sess = fernet().decrypt(SESSION_FILE.read_bytes()).decode()
    client = TelegramClient(StringSession(sess), API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        log("La sesión ya no es válida: vuelve a lanzar el modo login.")
        return
    bot = await client.get_entity(BOT)
    meta_path = pathlib.Path("data/sig.json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    for hh in ([] if os.environ.get("SOLO_COLORES") == "1" else HOURS):
        got = await ask(client, bot, f"/sig {hh} ibe")
        if not got:
            continue
        out = pathlib.Path(f"data/sig_{hh}.jpg")
        await client.download_media(got, file=str(out))
        meta[hh] = {"file": out.name, "received": int(got.date.timestamp()), "caption": (got.message or "")[:300]}
        log(f"/sig {hh} ibe: imagen guardada ({out.stat().st_size} bytes)")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    # Mapa de colores OTAN
    got = await ask(client, bot, "/colores")
    if got:
        out = pathlib.Path("data/colores.jpg")
        await client.download_media(got, file=str(out))
        pathlib.Path("data/colores.json").write_text(json.dumps(
            {"file": out.name, "received": int(got.date.timestamp())}))
        log(f"/colores: imagen guardada ({out.stat().st_size} bytes)")
    await client.disconnect()


if __name__ == "__main__":
    if not (API_ID and API_HASH and PHONE):
        log("Faltan los secretos TG_API_ID, TG_API_HASH o TG_PHONE.")
        sys.exit(0)
    mode = (sys.argv[1:] or ["fetch"])[0]
    asyncio.run(login() if mode == "login" else fetch())
