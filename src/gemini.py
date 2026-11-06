"""Llamadas a la Gemini API (capa gratuita): JSON, búsqueda web y análisis de video."""
import json
import re
import time

from google import genai
from google.genai import types

from .common import CONFIG, env

_cliente = None


def cliente():
    global _cliente
    if _cliente is None:
        _cliente = genai.Client(api_key=env("GEMINI_API_KEY"))
    return _cliente


def _a_json(texto):
    bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    return json.loads(bloque.group(1) if bloque else texto)


def _generar(contenidos, config, intentos=4):
    # La capa gratuita responde 429/503 cuando se pasa del límite por minuto: esperar y reintentar.
    for i in range(intentos):
        try:
            return cliente().models.generate_content(
                model=CONFIG["gemini"]["modelo"], contents=contenidos, config=config)
        except Exception as e:
            if getattr(e, "code", None) not in (429, 500, 503) or i == intentos - 1:
                raise
            time.sleep(30 * (i + 1))


def generar_json(prompt, adjuntos=(), **opciones):
    config = types.GenerateContentConfig(response_mime_type="application/json", **opciones)
    return _a_json(_generar([*adjuntos, prompt], config).text)


def buscar_en_web(prompt):
    """Respuesta con Google Search; el prompt debe pedir JSON (no se puede forzar con búsqueda activa)."""
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    return _a_json(_generar(prompt, config).text)


def subir_video(ruta):
    archivo = cliente().files.upload(file=str(ruta))
    while archivo.state.name == "PROCESSING":
        time.sleep(10)
        archivo = cliente().files.get(name=archivo.name)
    if archivo.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini no pudo procesar el video: {archivo.state.name}")
    return archivo


def borrar(archivo):
    cliente().files.delete(name=archivo.name)
