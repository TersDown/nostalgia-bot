"""Capítulo → resumen comentado: varios Reels verticales (uno por parte) + un video largo horizontal.

preparar() genera los videos y work/<id>/manifiesto.json; publicar() los programa en Facebook.
Con aprobacion.activa, entre uno y otro pasa por tu aprobación en Telegram (src/aprobar.py).

Uso local de prueba (solo genera los videos en work/):  python -m src.recap ruta/al/capitulo.mp4 --serie "Hey Arnold"
"""
import argparse
import asyncio
import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path

import edge_tts
from google.genai import types

from . import fb, gemini
from .common import CONFIG, TRABAJO, agregar_registro, ahora, leer_registro, proximos_horarios

R = CONFIG["resumen"]
T = CONFIG["tarjetas"]

FORMATOS = {
    "vertical": {"w": 1080, "h": 1920, "fuente": 64, "margen": 420},
    "horizontal": {"w": 1280, "h": 720, "fuente": 40, "margen": 45},
}
CODEC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]

PROMPT = """Eres el narrador de "{pagina}", una página de Facebook de nostalgia para Latinoamérica.
Mira este capítulo de "{serie}" y escribe el guion de un resumen comentado, en español latinoamericano neutro y con
voz propia de creador (cercana, con humor, como quien lo vio de niño y hoy lo vuelve a ver).
Reglas:
- Divide el capítulo en entre {pmin} y {pmax} partes consecutivas que cuenten la historia principal de principio a fin
  (omite intro, créditos y cortes comerciales). No las hagas iguales: corta donde la historia lo pida.
- Cada parte suma entre {wmin} y {wmax} palabras, nunca más (es un Reel de máximo 90 segundos). Para que quepa, salta
  escenas secundarias o de relleno: vale más un buen corte en suspenso que narrar todo.
- Cada parte, salvo la última, termina en un momento de suspenso del capítulo: una revelación a medias, una pregunta
  sin responder, un problema a punto de estallar. Su última frase deja esa intriga en el aire, sin revelar cómo se
  resuelve, para que el público quiera ver la siguiente parte.
- La primera frase de la parte 1 es un gancho que menciona la serie y despierta curiosidad (una pregunta, algo
  sorprendente o divertido). Nunca empieces con "En este capítulo". La primera frase de las demás partes menciona la
  serie y resume en una línea dónde quedó la historia, para quien llega directo a esa parte.
- Cuenta lo que pasa en orden, pero intercala comentarios tuyos: por qué la escena es memorable, detalles que casi nadie
  notó, chistes que de niños no entendíamos, cómo se veía en su época. Al menos una de cada tres frases debe ser
  comentario y no solo narración.
- Datos de producción o curiosidades solo si estás seguro de que son ciertos; si no, haz una observación propia.
- La última frase de la última parte es una opinión breve o una pregunta al público para que comente.
- Cada frase (1-2 oraciones) indica el tramo del capítulo que se verá mientras se escucha, con "inicio" y "fin" en
  MM:SS. En los comentarios, elige el momento al que se refieren. El tramo debe durar al menos lo que tarda en leerse
  la frase en voz alta.
- Usa los nombres de los personajes del doblaje latino.
Responde solo JSON:
{{"titulo_capitulo": "...", "descripcion": "1-2 oraciones para la publicación que terminen en una pregunta",
  "hashtags": ["#..."],
  "partes": [{{"titulo": "...", "frases": [{{"texto": "...", "inicio": "MM:SS", "fin": "MM:SS"}}]}}]}}"""


def ffmpeg(*args, cwd=None):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg falló: {r.stderr[-1500:]}")


def duracion(ruta):
    salida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                            capture_output=True, text=True, check=True).stdout
    return float(salida.strip())


def segundos(marca):
    total = 0.0
    for parte in str(marca).strip().split(":"):
        total = total * 60 + float(parte)
    return total


def temporada_episodio(nombre):
    m = re.search(r"[Ss](\d{1,2})[ ._-]?[EeXx](\d{1,3})", nombre) or re.search(r"\b(\d{1,2})x(\d{1,3})\b", nombre)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def narrar(texto, salida, intentos=4):
    # El servicio de voz falla de vez en cuando ("No audio was received"): esperar y reintentar.
    for i in range(intentos):
        try:
            return asyncio.run(edge_tts.Communicate(texto, R["voz"], rate=R["velocidad"]).save(str(salida)))
        except Exception:
            if i == intentos - 1:
                raise
            time.sleep(5 * (i + 1))


def narrar_parte(frases, carpeta, p):
    """Narra cada frase. Si el Reel (narración + cierre) pasaría de reel_max_seg, quita frases del medio: nunca la
    primera (gancho) ni la última (suspenso). Devuelve ([(frase, base, duración)], frases quitadas)."""
    narradas = []
    for f, frase in enumerate(frases, 1):
        base = carpeta / f"p{p:02d}f{f:03d}"
        narrar(frase["texto"], base.with_suffix(".mp3"))
        narradas.append((frase, base, duracion(base.with_suffix(".mp3"))))
    limite = R["reel_max_seg"] - T["segundos"] - 1  # 1 s de margen
    quitadas = 0
    while len(narradas) > 2 and sum(d for _, _, d in narradas) > limite:
        narradas.pop(len(narradas) // 2)
        quitadas += 1
    return narradas, quitadas


def cortes(inicio, fin, dur_audio, dur_capitulo):
    """Reparte la narración en cortes de <= fragmento_max_seg dentro del tramo indicado."""
    n = max(1, math.ceil(dur_audio / R["fragmento_max_seg"]))
    largo = dur_audio / n
    inicio = min(max(0.0, inicio), max(0.0, dur_capitulo - dur_audio))
    fin = min(max(fin, inicio + dur_audio), dur_capitulo)
    hueco = max(0.0, fin - inicio - largo)
    return [(inicio + (hueco * i / (n - 1) if n > 1 else 0), largo) for i in range(n)]


def filtro_formato(i, formato):
    if formato == "vertical":  # video centrado sobre una copia ampliada y desenfocada
        return (f"[{i}:v]split[a{i}][b{i}];"
                f"[a{i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg{i}];"
                f"[b{i}]scale=1080:-2[fg{i}];"
                f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,format=yuv420p[v{i}];")
    return (f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v{i}];")


def segmento(capitulo, lista_cortes, audio, dur_audio, formato, salida):
    """Un clip por frase: cortes del capítulo sin su audio + la narración de esa frase."""
    entradas, filtros = [], ""
    for i, (desde, largo) in enumerate(lista_cortes):
        entradas += ["-ss", f"{desde:.2f}", "-t", f"{largo:.2f}", "-i", capitulo]
        filtros += filtro_formato(i, formato)
    n = len(lista_cortes)
    filtros += "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc];[vc]tpad=stop_mode=clone:stop_duration=5[v]"
    ffmpeg(*entradas, "-i", audio, "-filter_complex", filtros, "-map", "[v]", "-map", f"{n}:a",
           "-t", f"{dur_audio:.3f}", *CODEC, salida)


def tarjeta(capitulo, desde, dur_capitulo, formato, salida):
    """Fondo del cierre: un tramo del capítulo desenfocado y oscurecido, sin sonido.
    El texto se le pone encima en unir(), junto con los subtítulos."""
    f, d = FORMATOS[formato], T["segundos"]
    desde = min(max(0.0, desde), max(0.0, dur_capitulo - d - 0.5))
    ffmpeg("-ss", f"{desde:.2f}", "-t", f"{d}", "-i", capitulo,
           "-f", "lavfi", "-t", f"{d}", "-i", "anullsrc=r=44100:cl=stereo",
           "-filter_complex",
           f"[0:v]scale={f['w']}:{f['h']}:force_original_aspect_ratio=increase,crop={f['w']}:{f['h']},"
           f"boxblur=25:5,eq=brightness=-0.3,setsar=1,fps=30,format=yuv420p,"
           f"tpad=stop_mode=clone:stop_duration={d}[v]",
           "-map", "[v]", "-map", "1:a", "-t", f"{d}", *CODEC, salida)
    return Path(salida)


def _ass(texto):
    return str(texto).replace("\\", "/").replace("{", "(").replace("}", ")")


def _titulo(*lineas):
    return r"\N".join(_ass(l) for l in lineas if l)


def _t(seg):
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def subtitulos(eventos, formato, total, salida):
    """eventos: [(texto, inicio, duración, estilo)]. "Sub" se divide en bloques de ~6 palabras; "Titulo" va entero."""
    f = FORMATOS[formato]
    estilo = ("{nombre},DejaVu Sans,{tam},{color},{color},{contorno},{fondo},-1,0,0,0,100,100,0,0,1,"
              "{borde},{sombra},{alin},60,60,{margen},1")
    lineas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {f['w']}", f"PlayResY: {f['h']}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        "Style: " + estilo.format(nombre="Sub", tam=f["fuente"], color="&H0000FFFF", contorno="&H00000000",
                                  fondo="&H64000000", borde=f["fuente"] // 12, sombra=2, alin=2, margen=f["margen"]),
        "Style: " + estilo.format(nombre="Titulo", tam=int(f["fuente"] * 1.25), color="&H00FFFFFF",
                                  contorno="&H00000000", fondo="&H64000000", borde=f["fuente"] // 10, sombra=3,
                                  alin=5, margen=0),
        "Style: " + estilo.format(nombre="Marca", tam=f["fuente"] // 2, color="&H60FFFFFF", contorno="&H80000000",
                                  fondo="&H00000000", borde=2, sombra=0, alin=8, margen=f["fuente"]),
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,{_t(0)},{_t(total)},Marca,,0,0,0,,{_ass(CONFIG['pagina']['nombre'])}",
    ]
    for texto, inicio, dur, nombre in eventos:
        if nombre == "Titulo":
            lineas.append(f"Dialogue: 0,{_t(inicio)},{_t(inicio + dur)},Titulo,,0,0,0,,{texto}")
            continue
        palabras = _ass(texto).split()
        bloques = [" ".join(palabras[i:i + 6]) for i in range(0, len(palabras), 6)]
        letras = sum(len(b) for b in bloques) or 1
        t = inicio
        for b in bloques:
            d = dur * len(b) / letras
            lineas.append(f"Dialogue: 0,{_t(t)},{_t(t + d)},Sub,,0,0,0,,{b}")
            t += d
    salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def unir(piezas, formato, carpeta, nombre):
    """piezas: [(ruta, texto, estilo)]. Las concatena y quema subtítulos, títulos y marca. Devuelve (ruta, duración)."""
    lista = carpeta / f"{nombre}.txt"
    lista.write_text("".join(f"file '{ruta.name}'\n" for ruta, _, _ in piezas), encoding="utf-8")
    eventos, t = [], 0.0
    for ruta, texto, estilo in piezas:
        d = duracion(ruta)
        eventos.append((texto, t, d, estilo))
        t += d
    subtitulos(eventos, formato, t, carpeta / f"{nombre}.ass")
    salida = carpeta / f"{nombre}.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", lista.name, "-vf", f"subtitles={nombre}.ass",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "copy", "-movflags", "+faststart",
           salida.name, cwd=carpeta)
    return salida, t


def generar(capitulo, serie, ident):
    """Crea los videos en work/<ident>/. Devuelve (guion, reels, largo, carpeta)."""
    capitulo = Path(capitulo).resolve()
    carpeta = TRABAJO / ident
    shutil.rmtree(carpeta, ignore_errors=True)
    carpeta.mkdir(parents=True)

    archivo = gemini.subir_video(capitulo)
    try:
        guion = gemini.generar_json(
            PROMPT.format(pagina=CONFIG["pagina"]["nombre"], serie=serie, pmin=R["partes_min"], pmax=R["partes_max"],
                          wmin=R["palabras_por_parte"][0], wmax=R["palabras_por_parte"][1]),
            adjuntos=[archivo], media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW)
    finally:
        gemini.borrar(archivo)

    dur_capitulo = duracion(capitulo)
    partes, n = guion["partes"], len(guion["partes"])
    cierre = _titulo(*T["cierre"])

    largo, reels = [], []
    for p, parte in enumerate(partes, 1):
        narradas, parte["omitidas"] = narrar_parte(parte["frases"], carpeta, p)
        parte["frases"] = frases = [frase for frase, _, _ in narradas]  # el guion guardado refleja lo que se oye
        piezas = []
        for frase, base, d in narradas:
            lista_cortes = cortes(segundos(frase["inicio"]), segundos(frase["fin"]), d, dur_capitulo)
            for formato, sufijo in (("vertical", "_v.mp4"), ("horizontal", "_h.mp4")):
                segmento(capitulo, lista_cortes, base.with_suffix(".mp3"), d, formato, Path(f"{base}{sufijo}"))
            piezas.append((Path(f"{base}_v.mp4"), frase["texto"], "Sub"))
            largo.append((Path(f"{base}_h.mp4"), frase["texto"], "Sub"))
        # Cierre: en las partes intermedias empuja a la siguiente; en la última, invita a comentar.
        texto_cierre = cierre if p == n else _titulo(*(l.format(siguiente=p + 1) for l in T["cierre_continua"]))
        piezas.append((tarjeta(capitulo, segundos(frases[-1]["inicio"]), dur_capitulo, "vertical",
                               carpeta / f"p{p:02d}_cierre_v.mp4"), texto_cierre, "Titulo"))
        ruta, d = unir(piezas, "vertical", carpeta, f"reel_{p:02d}")
        reels.append({"parte": p, "titulo": parte["titulo"], "archivo": ruta.name, "duracion": round(d, 1)})

    largo.append((tarjeta(capitulo, segundos(partes[-1]["frases"][-1]["inicio"]), dur_capitulo, "horizontal",
                          carpeta / "cierre_h.mp4"), cierre, "Titulo"))
    ruta, d = unir(largo, "horizontal", carpeta, "largo")
    return guion, reels, {"archivo": ruta.name, "duracion": round(d, 1)}, carpeta


def preparar(capitulo, serie, archivo_remoto):
    """Genera los videos y work/<id>/manifiesto.json, sin publicar nada. Devuelve (carpeta, manifiesto)."""
    nombre = Path(archivo_remoto).name
    ident = f"{re.sub(r'[^\w-]+', '_', Path(nombre).stem)[:28]}-{ahora():%m%d%H%M}"
    guion, reels, largo, carpeta = generar(capitulo, serie, ident)
    temporada, episodio = temporada_episodio(nombre)
    manifiesto = {"id": ident, "serie": serie, "archivo": archivo_remoto, "temporada": temporada,
                  "episodio": episodio, "creado": ahora().isoformat(), "guion": guion, "reels": reels, "largo": largo}
    (carpeta / "manifiesto.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1), encoding="utf-8")
    return carpeta, manifiesto


def publicar(carpeta):
    """Programa en Facebook los videos de work/<id>/. Si se corta a la mitad, al reintentar salta lo ya programado.
    Devuelve líneas de resumen para Telegram."""
    m = json.loads((Path(carpeta) / "manifiesto.json").read_text(encoding="utf-8"))
    guion, n = m["guion"], len(m["reels"])
    etiquetas = " ".join(guion.get("hashtags", []))
    base = {k: m[k] for k in ("serie", "archivo", "temporada", "episodio", "creado")}
    hechos = {(r["archivo"], r["tipo"], r.get("parte")) for r in leer_registro("videos")}
    resumen = []

    faltan = [r for r in m["reels"] if (m["archivo"], "reel", r["parte"]) not in hechos]
    for reel, cuando in zip(faltan, proximos_horarios("reel", len(faltan))):
        ruta = Path(carpeta) / reel["archivo"]
        texto = (f"{m['serie']}: {guion['titulo_capitulo']} — Parte {reel['parte']}/{n}: {reel['titulo']}\n\n"
                 f"{guion.get('descripcion', '')}\n\n{etiquetas}")
        if 3 <= reel["duracion"] <= R["reel_max_seg"]:
            fb_id = fb.programar_reel(ruta, texto, cuando)
        else:
            fb_id = fb.programar_video(ruta, f"{m['serie']} — Parte {reel['parte']}/{n}", texto, cuando)
        agregar_registro("videos", {**base, "tipo": "reel", "parte": reel["parte"], "fb_id": fb_id,
                                    "programado": cuando.isoformat(), "duracion": round(reel["duracion"])})
        resumen.append(f"• Reel {reel['parte']}/{n} → {cuando:%d/%m %H:%M}")

    if (m["archivo"], "largo", None) not in hechos:
        cuando = proximos_horarios("largo", 1)[0]
        titulo = f"{m['serie']}: {guion['titulo_capitulo']} | Resumen completo"
        fb_id = fb.programar_video(Path(carpeta) / m["largo"]["archivo"], titulo,
                                   f"{guion.get('descripcion', '')}\n\n{etiquetas}", cuando)
        agregar_registro("videos", {**base, "tipo": "largo", "parte": None, "fb_id": fb_id,
                                    "programado": cuando.isoformat(), "duracion": round(m["largo"]["duracion"])})
        resumen.append(f"• Video largo ({m['largo']['duracion'] / 60:.1f} min) → {cuando:%d/%m %H:%M}")
    return resumen


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("capitulo")
    ap.add_argument("--serie", required=True)
    a = ap.parse_args()
    _, reels, largo, carpeta = generar(a.capitulo, a.serie, re.sub(r"[^\w-]+", "_", Path(a.capitulo).stem))
    for r in reels:
        print(f"Reel {r['parte']}: {carpeta / r['archivo']} ({r['duracion']:.0f} s)")
    print(f"Largo: {carpeta / largo['archivo']} ({largo['duracion'] / 60:.1f} min)")
