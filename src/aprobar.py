"""Aprobación por Telegram de los videos ya generados.

pedir(carpeta, manifiesto)   te manda cada Reel con su guion y un mensaje con los botones
                             ✅ Aprobar / 🔁 Regenerar / 🗑 Descartar.
python -m src.aprobar        (workflow cada 10 min) lee los botones que tocaste y:
                             ✅ descarga los videos de pendientes/<id>/ y los programa en Facebook
                             🔁 devuelve el capítulo a entrada/ para generar un guion nuevo
                             🗑 borra los videos; el capítulo se queda en procesados/
Solo se aceptan botones tocados en tu chat (TELEGRAM_CHAT_ID).
"""
import json
import shutil
import subprocess

from . import recap
from .common import CONFIG, REMOTO, TRABAJO, dias_de_contenido, env, rclone, telegram, telegram_api

LIMITE_VIDEO = 49 * 1024 * 1024  # un bot de Telegram puede enviar videos de hasta 50 MB


def vista_previa(ruta):
    """Copia liviana (540 px) solo para verla en Telegram; a Facebook se sube el original."""
    salida = ruta.with_name(f"preview_{ruta.name}")
    recap.ffmpeg("-i", ruta, "-vf", "scale=540:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                 "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", salida)
    return salida


def pedir(carpeta, m):
    g, n, chat = m["guion"], len(m["reels"]), env("TELEGRAM_CHAT_ID")
    telegram(f"📝 Nuevo guion para revisar: {m['serie']} — {g['titulo_capitulo']}\n"
             f"{n} Reels + video largo ({m['largo']['duracion'] / 60:.1f} min). Los videos ya están listos.")
    for reel, parte in zip(m["reels"], g["partes"]):
        cabecera = f"🎬 Parte {reel['parte']}/{n}: {reel['titulo']} ({reel['duracion']:.0f} s)"
        if CONFIG["aprobacion"]["enviar_videos"]:
            try:
                ruta = vista_previa(carpeta / reel["archivo"])
                if ruta.stat().st_size >= LIMITE_VIDEO:
                    raise RuntimeError("pesa más de 50 MB")
                with open(ruta, "rb") as f:
                    telegram_api("sendVideo", files={"video": f}, chat_id=chat, caption=cabecera,
                                 supports_streaming="true")
            except Exception as e:
                telegram(f"(No se pudo enviar el video de la parte {reel['parte']}: {str(e)[:200]}. "
                         f"Está en Drive: pendientes/{m['id']}/{reel['archivo']})")
        nota = (f"\n\n(Se quitaron {parte['omitidas']} frase(s) del medio para no pasar de 90 s.)"
                if parte.get("omitidas") else "")
        telegram(f"{cabecera}\n\n" + " ".join(fr["texto"] for fr in parte["frases"]) + nota)

    botones = {"inline_keyboard": [
        [{"text": "✅ Aprobar y programar", "callback_data": f"ok:{m['id']}"}],
        [{"text": "🔁 Regenerar", "callback_data": f"re:{m['id']}"},
         {"text": "🗑 Descartar", "callback_data": f"no:{m['id']}"}]]}
    telegram_api("sendMessage", chat_id=chat, reply_markup=json.dumps(botones), text=(
        f"📣 Texto de la publicación:\n{g.get('descripcion', '')}\n{' '.join(g.get('hashtags', []))}\n\n"
        f"¿Programo {m['serie']} — {g['titulo_capitulo']}?\n"
        f"(Se aplica en la próxima revisión, máx. ~15 min.)\nID: {m['id']}"))


def _existe(remoto):
    try:
        rclone("lsf", remoto)
        return True
    except subprocess.CalledProcessError:
        return False


def ejecutar(accion, ident):
    remoto = f"{REMOTO}/pendientes/{ident}"
    if not ident or not _existe(remoto):
        return f"ℹ️ {ident}: ya se había resuelto antes."
    if accion == "ok":
        carpeta = TRABAJO / ident
        shutil.rmtree(carpeta, ignore_errors=True)
        rclone("copy", remoto, str(carpeta))
        resumen = recap.publicar(carpeta)
        rclone("purge", remoto)
        return ("✅ Aprobado y programado:\n" + "\n".join(resumen) +
                f"\n\nContenido programado: {dias_de_contenido():.1f} días.")
    if accion == "re":
        m = json.loads(rclone("cat", f"{remoto}/manifiesto.json"))
        rclone("moveto", f"{REMOTO}/procesados/{m['archivo']}", f"{REMOTO}/entrada/{m['archivo']}")
        rclone("purge", remoto)
        return "🔁 Se generará un guion nuevo en la próxima revisión de la carpeta (≤ 30 min)."
    if accion == "no":
        rclone("purge", remoto)
        return "🗑 Descartado. El capítulo queda en procesados/."
    return f"Acción desconocida: {accion}"


def revisar():
    chat = str(env("TELEGRAM_CHAT_ID"))
    updates = telegram_api("getUpdates", timeout=0, allowed_updates=json.dumps(["callback_query"]))
    if not updates:
        print("Sin botones tocados.")
        return
    # Confirmarlas ya, para que Telegram no las vuelva a entregar. Si algo falla, el botón sigue en el mensaje
    # y basta con tocarlo otra vez.
    telegram_api("getUpdates", timeout=0, offset=updates[-1]["update_id"] + 1)

    for u in updates:
        cq = u.get("callback_query")
        if not cq or "message" not in cq or str(cq["message"]["chat"]["id"]) != chat:
            continue
        accion, _, ident = cq.get("data", "").partition(":")
        try:
            telegram_api("answerCallbackQuery", callback_query_id=cq["id"], text="Recibido")
        except Exception:
            pass  # Telegram no deja responder botones de hace más de unos segundos; no importa
        print(f"{accion} {ident}")
        try:
            resultado = ejecutar(accion, ident)
        except Exception as e:
            telegram(f"❌ Error con {ident}: {str(e)[:1500]}\nToca el botón otra vez para reintentar.")
            continue
        try:
            telegram_api("editMessageText", chat_id=chat, message_id=cq["message"]["message_id"],
                         text=f"{cq['message'].get('text', '')}\n\n{resultado}"[:4000])
        except Exception:
            telegram(resultado)


if __name__ == "__main__":
    revisar()
