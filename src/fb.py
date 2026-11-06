"""Publicación en la página vía Meta Graph API."""
import os

import requests

from .common import CONFIG, env

V = CONFIG["pagina"]["graph_api"]
GRAPH = f"https://graph.facebook.com/{V}"


def _credenciales():
    return env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")


def _revisar(r):
    datos = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in datos:
        raise RuntimeError(f"Graph API {r.status_code}: {datos.get('error', r.text)}")
    return datos


def verificar_token():
    pagina, token = _credenciales()
    r = requests.get(f"{GRAPH}/{pagina}", params={"fields": "name", "access_token": token}, timeout=30)
    return _revisar(r)["name"]


def publicar_foto(url, mensaje):
    pagina, token = _credenciales()
    r = requests.post(f"{GRAPH}/{pagina}/photos",
                      data={"url": url, "message": mensaje, "access_token": token}, timeout=60)
    return _revisar(r)["id"]


def programar_reel(ruta, descripcion, cuando):
    pagina, token = _credenciales()
    inicio = _revisar(requests.post(f"{GRAPH}/{pagina}/video_reels",
                                    data={"upload_phase": "start", "access_token": token}, timeout=60))
    with open(ruta, "rb") as f:
        _revisar(requests.post(inicio["upload_url"], data=f, timeout=900, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(os.path.getsize(ruta))}))
    _revisar(requests.post(f"{GRAPH}/{pagina}/video_reels", timeout=60, data={
        "upload_phase": "finish", "video_id": inicio["video_id"], "video_state": "SCHEDULED",
        "scheduled_publish_time": int(cuando.timestamp()), "description": descripcion, "access_token": token}))
    return inicio["video_id"]


def programar_video(ruta, titulo, descripcion, cuando):
    pagina, token = _credenciales()
    with open(ruta, "rb") as f:
        r = requests.post(f"https://graph-video.facebook.com/{V}/{pagina}/videos", files={"source": f},
                          timeout=1800, data={
                              "title": titulo, "description": descripcion, "published": "false",
                              "scheduled_publish_time": int(cuando.timestamp()), "access_token": token})
    return _revisar(r)["id"]


def interacciones(objeto_id):
    """Reacciones + comentarios de una foto o video publicado."""
    _, token = _credenciales()
    campos = "reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)"
    datos = _revisar(requests.get(f"{GRAPH}/{objeto_id}",
                                  params={"fields": campos, "access_token": token}, timeout=30))
    return sum(datos.get(k, {}).get("summary", {}).get("total_count", 0) for k in ("reactions", "comments"))
