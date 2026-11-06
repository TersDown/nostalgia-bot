"""Recomendador editorial por Telegram.

Domingos: informe completo (ranking de tus series, tendencias, fechas especiales y siguiente capítulo).
Otros días: solo avisa si quedan menos de alertas.dias_minimos días de Reels programados.
Solo sugiere series y capítulos; no busca ni enlaza descargas.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

import requests

from . import fb, gemini
from .common import CONFIG, ahora, dias_de_contenido, leer_registro, series_activas, telegram

TENDENCIAS = """Hoy es {hoy}. Mi página de Facebook publica resúmenes y memes de series y caricaturas clásicas
(años 80, 90 y 2000) para público de Latinoamérica. Series actuales: {series}.
Busca en la web y dime:
1. Hasta 5 series o caricaturas (de mi lista o nuevas) que sean tendencia en LATAM esta semana o las próximas dos
   (estrenos, remakes, aniversarios, noticias, memes virales) y por qué.
2. Hasta 4 fechas de los próximos 14 días (festividades, aniversarios) con un capítulo temático concreto que encaje.
Responde solo un bloque ```json``` con:
{{"tendencias": [{{"serie": "...", "motivo": "..."}}], "fechas": [{{"fecha": "DD/MM", "serie": "...", "capitulo": "...", "motivo": "..."}}]}}"""


def episodios(nombre_tvmaze):
    r = requests.get("https://api.tvmaze.com/singlesearch/shows",
                     params={"q": nombre_tvmaze, "embed": "episodes"}, timeout=30)
    return r.json().get("_embedded", {}).get("episodes", []) if r.ok else []


def siguiente_y_aniversarios(serie):
    eps = [e for e in episodios(serie["tvmaze"]) if e.get("season") and e.get("number")]
    hechos = [(r["temporada"], r["episodio"]) for r in leer_registro("videos")
              if r["serie"] == serie["carpeta"] and r.get("temporada")]
    ultimo = max(hechos, default=(0, 0))
    siguiente = next((e for e in eps if (e["season"], e["number"]) > ultimo), None)

    hoy = ahora().date()
    proximos = {(hoy + timedelta(days=d)).strftime("%m-%d") for d in range(8)}
    aniversarios = [e for e in eps if e.get("airdate") and e["airdate"][5:] in proximos][:2]
    return siguiente, aniversarios


def etiqueta(e):
    return f'T{e["season"]}E{e["number"]} "{e["name"]}"'


def ranking(dias=30):
    """Interacciones promedio por serie en publicaciones de los últimos `dias` (con al menos 24 h al aire)."""
    desde, hasta = ahora() - timedelta(days=dias), ahora() - timedelta(hours=24)
    puntos = defaultdict(list)
    for r in leer_registro("videos") + leer_registro("memes"):
        cuando = datetime.fromisoformat(r.get("programado") or r["publicado"])
        if desde <= cuando <= hasta:
            try:
                puntos[r["serie"]].append(fb.interacciones(r["fb_id"]))
            except Exception as e:
                print(f"Sin métricas para {r['fb_id']}: {e}")
    return sorted(((s, sum(v) / len(v), len(v)) for s, v in puntos.items()), key=lambda x: -x[1])


def informe_semanal(dias):
    lineas = [f"📺 Sugerencias de la semana (te quedan {dias:.1f} días de Reels programados)", ""]

    tabla = ranking()
    if tabla:
        lineas.append("🏆 Tus series (interacciones promedio, últimos 30 días):")
        lineas += [f"  {i}. {s}: {prom:.0f} ({n} publicaciones)" for i, (s, prom, n) in enumerate(tabla[:6], 1)]
        if len(tabla) > 2:
            lineas.append(f"  ↓ Menor rendimiento: {tabla[-1][0]}; considera pausarla en config.yaml")
        lineas.append("")

    lineas.append("➡️ Siguiente capítulo por serie:")
    aniversarios = []
    for s in series_activas():
        sig, anv = siguiente_y_aniversarios(s)
        lineas.append(f"  • {s['carpeta']}: {etiqueta(sig) if sig else '(sin datos en TVmaze)'}")
        aniversarios += [(s["carpeta"], e) for e in anv]
    if aniversarios:
        lineas += ["", "🎂 Aniversarios de estreno esta semana:"]
        lineas += [f"  • {serie}: {etiqueta(e)}, estrenado el {e['airdate']}" for serie, e in aniversarios]

    try:
        t = gemini.buscar_en_web(TENDENCIAS.format(hoy=ahora().strftime("%d/%m/%Y"),
                                                   series=", ".join(s["carpeta"] for s in series_activas())))
        if t.get("tendencias"):
            lineas += ["", "🔥 Tendencias en LATAM:"]
            lineas += [f"  • {x['serie']}: {x['motivo']}" for x in t["tendencias"]]
        if t.get("fechas"):
            lineas += ["", "📅 Fechas próximas:"]
            lineas += [f"  • {x['fecha']} {x['serie']} — {x['capitulo']} ({x['motivo']})" for x in t["fechas"]]
    except Exception as e:
        lineas += ["", f"(No se pudieron consultar tendencias: {e})"]
    return "\n".join(lineas)


def aviso_diario(dias):
    lineas = [f"⏳ Quedan {dias:.1f} días de Reels programados. Agrega capítulos a entrada/. Sugerencias:"]
    for s in series_activas():
        sig, _ = siguiente_y_aniversarios(s)
        if sig:
            lineas.append(f"  • {s['carpeta']}: {etiqueta(sig)}")
    return "\n".join(lineas)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--semanal", action="store_true", help="forzar el informe completo")
    a = ap.parse_args()
    dias = dias_de_contenido()
    if a.semanal or ahora().weekday() == 6:
        telegram(informe_semanal(dias))
    elif dias < CONFIG["alertas"]["dias_minimos"]:
        telegram(aviso_diario(dias))
    else:
        print(f"Hay {dias:.1f} días de contenido; sin aviso.")
