"""Carpeta vigilada en Drive/OneDrive (rclone).

--revisar            escribe en GITHUB_OUTPUT el primer archivo nuevo de entrada/ (o nada)
--procesar ARCHIVO   lo descarga, genera los videos y los deja en pendientes/<id>/ esperando tu aprobación en Telegram
                     (o los programa directo si aprobacion.activa es false). El capítulo pasa a procesados/.
"""
import argparse
import json
import os
from pathlib import Path

from . import aprobar, recap
from .common import CONFIG, REMOTO, TRABAJO, dias_de_contenido, leer_registro, rclone, telegram

# Lo único que se sube a pendientes/: los videos finales y el manifiesto (no los cortes intermedios).
FINALES = ["--include", "reel_*.mp4", "--include", "largo.mp4", "--include", "manifiesto.json"]


def nuevos():
    archivos = json.loads(rclone("lsjson", "--recursive", "--files-only", f"{REMOTO}/entrada"))
    hechos = {r["archivo"] for r in leer_registro("videos")}
    extensiones = set(CONFIG["almacenamiento"]["extensiones"])
    return sorted(a["Path"] for a in archivos
                  if Path(a["Path"]).suffix.lower() in extensiones and a["Path"] not in hechos)


def revisar():
    pendientes = nuevos()
    print(f"{len(pendientes)} archivo(s) nuevo(s)" + (f"; siguiente: {pendientes[0]}" if pendientes else ""))
    if pendientes and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"archivo={pendientes[0]}\n")


def procesar(archivo):
    partes = Path(archivo).parts
    serie = partes[0] if len(partes) > 1 else Path(archivo).stem
    con_aprobacion = CONFIG["aprobacion"]["activa"]
    TRABAJO.mkdir(exist_ok=True)
    local = TRABAJO / f"capitulo{Path(archivo).suffix}"
    try:
        rclone("copyto", f"{REMOTO}/entrada/{archivo}", str(local))
        carpeta, manifiesto = recap.preparar(local, serie, archivo)
        if con_aprobacion:
            rclone("copy", str(carpeta), f"{REMOTO}/pendientes/{manifiesto['id']}", *FINALES)
        else:
            resumen = recap.publicar(carpeta)
    except Exception as e:
        rclone("moveto", f"{REMOTO}/entrada/{archivo}", f"{REMOTO}/errores/{archivo}")
        telegram(f"❌ Error con {archivo} (movido a errores/):\n{str(e)[:1500]}")
        raise
    rclone("moveto", f"{REMOTO}/entrada/{archivo}", f"{REMOTO}/procesados/{archivo}")
    if con_aprobacion:
        aprobar.pedir(carpeta, manifiesto)
    else:
        telegram(f"✅ {serie} — {manifiesto['guion']['titulo_capitulo']}\n" + "\n".join(resumen) +
                 f"\n\nContenido programado: {dias_de_contenido():.1f} días. Pendientes en la carpeta: {len(nuevos())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--revisar", action="store_true")
    grupo.add_argument("--procesar")
    a = ap.parse_args()
    revisar() if a.revisar else procesar(a.procesar)
