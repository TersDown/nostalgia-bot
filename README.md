# Nostalgia Animada: página de Facebook automatizada

Todo corre en GitHub Actions (gratis). Tu PC solo se usa para la configuración inicial.

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `memes.yml` | 11:00, 15:00 y 22:30 (México) | Gemini elige plantilla y textos → Imgflip crea la imagen → se publica. Filtro automático, sin revisión manual |
| `resumenes.yml` | cada 30 min | Si hay un capítulo nuevo en `entrada/<serie>/`, genera los Reels y el video largo, los deja en `pendientes/<id>/` y te los manda a Telegram con botones |
| `aprobaciones.yml` | cada 10 min | Aplica los botones que tocaste: ✅ programa en Facebook, 🔁 regenera el guion, 🗑 descarta |
| `recomendaciones.yml` | 9:00 diario | Domingos: informe completo. Otros días: aviso solo si quedan menos de 3 días de contenido |

El estado (qué se publicó y cuándo) queda en `data/videos.jsonl` y `data/memes.jsonl`.

## Configuración inicial (una sola vez)

### 1. Página y token de Facebook
1. Crea la página (categoría *Página de entretenimiento*) con logo y portada.
2. En [developers.facebook.com](https://developers.facebook.com/apps) → **Crear app** → tipo *Business*.
3. Abre el [Graph API Explorer](https://developers.facebook.com/tools/explorer/), elige tu app y genera un **User Token** con los permisos
   `pages_show_list`, `pages_manage_posts`, `pages_read_engagement` y `read_insights`.
4. Cámbialo por uno de larga duración (en el navegador):
   `https://graph.facebook.com/v23.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=TOKEN_CORTO`
5. Con ese token llama a `https://graph.facebook.com/v23.0/me/accounts?access_token=TOKEN_LARGO`. Ahí obtienes el `id`
   de la página (**FB_PAGE_ID**) y su `access_token` (**FB_PAGE_TOKEN**). Revísalo en el
   [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/): debe decir *Expires: Never*.

### 2. Otras claves (todas gratuitas)
- **GEMINI_API_KEY**: [aistudio.google.com](https://aistudio.google.com/apikey) → *Create API key*.
- **IMGFLIP_USER / IMGFLIP_PASS**: crea una cuenta en [imgflip.com](https://imgflip.com/signup).
- **TELEGRAM_TOKEN**: en Telegram, habla con `@BotFather` → `/newbot`.
- **TELEGRAM_CHAT_ID**: mándale cualquier mensaje a tu bot y abre
  `https://api.telegram.org/bot<TOKEN>/getUpdates`; el número está en `"chat":{"id": ...}`.

### 3. Carpeta vigilada (rclone)
1. Instala rclone una vez: `winget install Rclone.Rclone`.
2. `rclone config` → *n* (nuevo) → nombre `drive` → tipo *Google Drive* (u *OneDrive*) → acepta los valores por defecto y autoriza en el navegador.
3. En tu Drive crea `Nostalgia/entrada/`, `Nostalgia/procesados/`, `Nostalgia/errores/` y `Nostalgia/pendientes/`.
   Dentro de `entrada/`, una subcarpeta por serie con **el mismo nombre que `carpeta` en `config.yaml`**.
4. `rclone config file` te dice dónde está `rclone.conf`; su contenido completo es el secret **RCLONE_CONF**.

Si nombras los archivos con `S01E05` o `1x05`, el recomendador sabe qué capítulo sigue.

### 4. Repositorio en GitHub
1. Crea un repositorio **público** (los minutos de Actions son ilimitados; en uno privado solo tienes 2000 al mes y la
   carpeta vigilada cada 30 min los agota. Si lo prefieres privado, cambia el cron de `resumenes.yml` a cada 3 horas).
   Los secrets nunca son visibles, aunque el repositorio sea público.
2. Sube esta carpeta:
   ```
   git init && git add . && git commit -m "Inicio" && git branch -M main
   git remote add origin https://github.com/TU_USUARIO/TU_REPO.git && git push -u origin main
   ```
3. *Settings → Secrets and variables → Actions → New repository secret*: crea los 8 secrets
   `FB_PAGE_ID`, `FB_PAGE_TOKEN`, `GEMINI_API_KEY`, `IMGFLIP_USER`, `IMGFLIP_PASS`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` y `RCLONE_CONF`.
4. Edita `config.yaml`: nombre de la página, series y horarios.

## Prueba de arranque (en este orden)
1. *Actions → Memes → Run workflow* → el meme aparece en la página.
2. Pon un capítulo en `entrada/<serie>/` → *Actions → Carpeta vigilada → Run workflow* → llegan a Telegram los Reels y
   el guion con botones → toca ✅ → *Actions → Aprobaciones → Run workflow* → los videos aparecen en
   *Meta Business Suite → Planificador*.
3. *Actions → Recomendaciones → Run workflow* (con "semanal" marcado) → llega el informe a Telegram.
4. Dos días después, revisa que los cron publiquen solos y que `data/*.jsonl` se vaya actualizando.

## Ajustes frecuentes
- **Voz, duración y número de partes**: `resumen` en `config.yaml`.
- **Pausar una serie**: `activa: false`.
- **Modelo de Gemini**: si Google retira `gemini-3.8-flash`, cámbialo en `gemini.modelo` por el flash gratuito vigente.
- **GitHub pausa los cron** de un repositorio público tras 60 días sin commits. Los commits de estado lo mantienen activo
  mientras haya publicaciones.

## Riesgos
Los videos que usan imágenes de capítulos con derechos pueden recibir reclamaciones de Rights Manager: bloqueo,
ingresos para el titular o restricciones a la página. Revisa *Business Suite → Calidad de la página* cada semana. Si una
serie acumula reclamaciones, ponla en `activa: false`.
