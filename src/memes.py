"""Genera y publica un meme: Gemini elige plantilla y textos, Imgflip crea la imagen, Graph API la publica."""
import random
import re

import requests

from . import fb, gemini
from .common import CONFIG, agregar_registro, ahora, env, series_activas, telegram

IMGFLIP = "https://api.imgflip.com"

PROMPT = """Eres el community manager de "{pagina}", una página de Facebook de nostalgia para Latinoamérica.
Crea UN meme sobre la serie "{serie}" usando una de estas plantillas de Imgflip:
{plantillas}

Reglas:
- Español latinoamericano, humor blanco y nostálgico (la infancia, los 90 y 2000, ver la tele al volver de la escuela).
- Referencias reconocibles a personajes, frases o momentos de la serie (nombres del doblaje latino).
- Máximo 12 palabras por caja. Sin groserías, política ni temas sensibles.
- El número de textos debe ser exactamente el número de cajas de la plantilla elegida.

Responde solo JSON:
{{"template_id": "...", "textos": ["caja 1", "caja 2"], "descripcion": "texto corto para la publicación que termine en una pregunta", "hashtags": ["#..."]}}"""

FILTRO = """Revisa este meme antes de publicarlo en una página familiar de Facebook.
Serie: {serie}. Plantilla: {plantilla}. Textos: {textos}. Descripción: {descripcion}
¿Es ofensivo, sexual, político, discriminatorio, o no se entiende como chiste?
Responde solo JSON: {{"ok": true o false, "motivo": "..."}}"""


def plantillas():
    return requests.get(f"{IMGFLIP}/get_memes", timeout=30).json()["data"]["memes"]


def proponer(serie, todas):
    """Devuelve (idea, plantilla) o (None, motivo del descarte)."""
    muestra = random.sample(todas, min(CONFIG["memes"]["plantillas_a_considerar"], len(todas)))
    lista = "\n".join(f'- id {p["id"]}: "{p["name"]}" ({p["box_count"]} cajas)' for p in muestra)
    idea = gemini.generar_json(PROMPT.format(pagina=CONFIG["pagina"]["nombre"], serie=serie, plantillas=lista))

    plantilla = next((p for p in muestra if str(p["id"]) == str(idea.get("template_id"))), None)
    if not plantilla or len(idea.get("textos", [])) != plantilla["box_count"]:
        return None, "plantilla inexistente o número de textos incorrecto"

    texto = " ".join(idea["textos"] + [idea.get("descripcion", "")]).lower()
    for palabra in CONFIG["memes"]["palabras_prohibidas"]:
        if re.search(rf"\b{re.escape(palabra.lower())}", texto):
            return None, f"palabra prohibida: {palabra}"

    revision = gemini.generar_json(FILTRO.format(serie=serie, plantilla=plantilla["name"],
                                                 textos=idea["textos"], descripcion=idea.get("descripcion", "")))
    if not revision.get("ok"):
        return None, f"filtro: {revision.get('motivo', 'rechazado')}"
    return idea, plantilla


def crear_imagen(plantilla_id, textos):
    datos = {"template_id": plantilla_id, "username": env("IMGFLIP_USER"), "password": env("IMGFLIP_PASS")}
    for i, t in enumerate(textos):
        datos[f"boxes[{i}][text]"] = t
    r = requests.post(f"{IMGFLIP}/caption_image", data=datos, timeout=60).json()
    if not r.get("success"):
        raise RuntimeError(f"Imgflip: {r.get('error_message')}")
    return r["data"]["url"]


def main():
    todas = plantillas()
    serie = random.choice(series_activas())["carpeta"]
    for intento in range(1, CONFIG["memes"]["intentos"] + 1):
        idea, plantilla_o_motivo = proponer(serie, todas)
        if idea:
            plantilla = plantilla_o_motivo
            break
        print(f"Intento {intento} descartado ({plantilla_o_motivo})")
    else:
        telegram(f"⚠️ Memes: ningún meme de {serie} pasó el filtro en {intento} intentos.")
        raise SystemExit(1)

    url = crear_imagen(plantilla["id"], idea["textos"])
    mensaje = f'{idea.get("descripcion", "")}\n\n{" ".join(idea.get("hashtags", []))}'.strip()
    fb_id = fb.publicar_foto(url, mensaje)
    agregar_registro("memes", {"serie": serie, "plantilla": plantilla["name"], "textos": idea["textos"],
                               "imagen": url, "fb_id": fb_id, "publicado": ahora().isoformat()})
    print(f"Meme publicado: {fb_id} ({serie} / {plantilla['name']})")


if __name__ == "__main__":
    main()
