"""Llamadas a la Gemini API (capa gratuita): JSON, búsqueda web y análisis de video."""
import json
import re
import time

from google import genai
from google.genai import types

from .common import CONFIG, env

G = CONFIG["gemini"]
_cliente = None


def cliente():
    global _cliente
    if _cliente is None:
        # Límite de espera por llamada: sin esto, una conexión colgada puede tardar minutos en fallar.
        _cliente = genai.Client(api_key=env("GEMINI_API_KEY"),
                                http_options=types.HttpOptions(timeout=int(G.get("timeout_seg", 180) * 1000)))
    return _cliente


def _a_json(texto):
    bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    return json.loads(bloque.group(1) if bloque else texto)


def _generar(contenidos, config, intentos=4):
    """Reintenta si Google está saturado (429/5xx) o si la conexión se corta o se pasa del tiempo de espera.
    Los demás errores (clave inválida, modelo inexistente...) se lanzan de inmediato."""
    nivel = G.get("razonamiento")
    if nivel and config.thinking_config is None:
        config.thinking_config = types.ThinkingConfig(thinking_level=nivel.upper())
    for i in range(intentos):
        try:
            return cliente().models.generate_content(model=G["modelo"], contents=contenidos, config=config)
        except Exception as e:
            codigo = getattr(e, "code", None)
            if codigo == 400 and "think" in str(e).lower() and config.thinking_config is not None:
                print("El modelo no acepta 'razonamiento'; sigo sin esa opción.")
                config.thinking_config = None
                continue
            if (codigo is not None and codigo not in (429, 500, 502, 503, 504)) or i == intentos - 1:
                raise
            print(f"Gemini falló ({codigo or type(e).__name__}); reintento {i + 2}/{intentos}...")
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
