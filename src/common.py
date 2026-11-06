"""Configuración, registro de publicaciones (data/*.jsonl), horarios, rclone y Telegram."""
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
TRABAJO = RAIZ / "work"
CONFIG = yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))
TZ = ZoneInfo(CONFIG["pagina"]["zona_horaria"])
REMOTO = CONFIG["almacenamiento"]["remoto"]

# .env opcional para pruebas locales; en GitHub Actions las variables vienen de Secrets.
_env = RAIZ / ".env"
if _env.exists():
    for linea in _env.read_text(encoding="utf-8").splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def env(nombre):
    valor = os.environ.get(nombre)
    if not valor:
        raise SystemExit(f"Falta la variable de entorno {nombre}")
    return valor


def ahora():
    return datetime.now(TZ)


def leer_registro(nombre):
    ruta = DATA / f"{nombre}.jsonl"
    if not ruta.exists():
        return []
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def agregar_registro(nombre, fila):
    DATA.mkdir(exist_ok=True)
    with open(DATA / f"{nombre}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def telegram(texto):
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[telegram no configurado]\n" + texto)
        return
    # Telegram acepta hasta 4096 caracteres por mensaje: los textos largos van en varios.
    while texto:
        corte = len(texto) if len(texto) <= 4000 else (texto.rfind(" ", 0, 4000) + 1 or 4000)
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": texto[:corte]}, timeout=30)
        texto = texto[corte:]


def telegram_api(metodo, files=None, **datos):
    """Llamada directa a la Bot API (botones, videos, getUpdates). Lanza error si Telegram responde ok=false."""
    r = requests.post(f"https://api.telegram.org/bot{env('TELEGRAM_TOKEN')}/{metodo}",
                      data=datos, files=files, timeout=300).json()
    if not r.get("ok"):
        raise RuntimeError(f"Telegram {metodo}: {r.get('description')}")
    return r["result"]


def rclone(*args):
    return subprocess.run(["rclone", *args], check=True, capture_output=True, text=True).stdout


def series_activas():
    return [s for s in CONFIG["series"] if s.get("activa", True)]


def programados_futuros(tipo):
    limite = ahora()
    fechas = (datetime.fromisoformat(r["programado"]) for r in leer_registro("videos") if r["tipo"] == tipo)
    return [f for f in fechas if f > limite]


def proximos_horarios(tipo, n):
    """n fechas libres según config.horarios[tipo], al menos 30 min en el futuro (Meta pide >10 min)."""
    minimo = ahora() + timedelta(minutes=30)
    ocupados = set(programados_futuros(tipo))
    libres, dia = [], minimo.date()
    while len(libres) < n:
        for hhmm in CONFIG["horarios"][tipo]:
            h, m = map(int, hhmm.split(":"))
            t = datetime(dia.year, dia.month, dia.day, h, m, tzinfo=TZ)
            if t >= minimo and t not in ocupados and len(libres) < n:
                libres.append(t)
        dia += timedelta(days=1)
    return libres


def dias_de_contenido():
    return len(programados_futuros("reel")) / len(CONFIG["horarios"]["reel"])
