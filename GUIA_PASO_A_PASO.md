# Guía paso a paso: dejar la página funcionando

Tiempo total estimado: **3 a 4 horas**, una sola vez. Marca cada casilla al terminarla.

Al final vas a tener:
- 3 memes al día publicados solos.
- Cada vez que dejas un capítulo en tu Google Drive, el bot lo parte en 3 a 6 Reels de máximo 90 s que cortan en los
  momentos de suspenso (voz de IA, subtítulos y cierre que invita a ver la siguiente parte), más un video largo, y te
  los manda a Telegram con el guion. **Nada se publica hasta que tocas ✅ Aprobar.**
- Avisos y recomendaciones por Telegram.

Todo corre en GitHub Actions (gratis). Tu PC solo se usa para esta configuración.

> **Antes de empezar:** abre un bloc de notas y llámalo `claves.txt`. Ahí vas a ir pegando las 8 claves que juntas
> en esta guía. **No lo subas a ningún lado** y bórralo al terminar el Paso 9.
>
> | Clave | Se obtiene en |
> |---|---|
> | `FB_PAGE_ID` | Paso 2 |
> | `FB_PAGE_TOKEN` | Paso 2 |
> | `GEMINI_API_KEY` | Paso 3 |
> | `IMGFLIP_USER` | Paso 4 |
> | `IMGFLIP_PASS` | Paso 4 |
> | `TELEGRAM_TOKEN` | Paso 5 |
> | `TELEGRAM_CHAT_ID` | Paso 5 |
> | `RCLONE_CONF` | Paso 6 |

---

## Paso 0: Requisitos y seguridad (10 min)

- [ ] Tienes una cuenta personal de Facebook (será la administradora de la página).
- [ ] **Activa la verificación en dos pasos** en esa cuenta: *Facebook → Configuración → Centro de cuentas → Contraseña y
      seguridad → Autenticación en dos pasos*. El token que vas a crear puede publicar en tu página, y si te roban la
      cuenta, te roban la página.
- [ ] Tienes una cuenta de Google (para Gemini y Drive).
- [ ] Tienes Telegram instalado en el celular o en la PC.

---

## Paso 1: Crear la página de Facebook (20 min)

1. [ ] Entra a <https://www.facebook.com/pages/create>.
2. [ ] **Nombre**: el que quieras (por ejemplo "Nostalgia Animada"). Anótalo: va en `config.yaml`.
3. [ ] **Categoría**: escribe *Página de entretenimiento* (o *Sitio web de entretenimiento*).
4. [ ] **Biografía**: una línea, por ejemplo "Revive las caricaturas y series de tu infancia 📺".
5. [ ] Clic en **Crear página**.
6. [ ] Sube la **foto de perfil** (logo cuadrado) y la **portada** (1640×624). Puedes hacerlas gratis en Canva.
7. [ ] *Configuración de la página → Nombre de usuario*: elige un @usuario corto.
8. [ ] En la página, cambia a tu perfil de página y revisa que aparezca **Meta Business Suite**
      (<https://business.facebook.com>). Ahí vas a ver las publicaciones programadas, en *Planificador*.
9. [ ] Si aparece la opción **Activar modo profesional**, actívala (da acceso a estadísticas y monetización).

---

## Paso 2: Token de la página (Meta for Developers) (40 min)

Este es el paso más técnico. Síguelo al pie de la letra.

### 2.1 Cuenta de desarrollador
1. [ ] Entra a <https://developers.facebook.com> con tu cuenta personal.
2. [ ] Clic en **Empezar** (Get Started) → acepta los términos → verifica tu teléfono o correo si te lo pide → como
      ocupación, elige *Desarrollador*.

### 2.2 Crear la app
1. [ ] <https://developers.facebook.com/apps> → **Crear app**.
2. [ ] Nombre de la app: por ejemplo `nostalgia-bot`. Correo: el tuyo.
3. [ ] **Caso de uso**: elige **"Administrar todo en tu página"** (*Manage everything on your Page*). Si tu pantalla
      muestra otra versión del asistente, elige **"Otro"** y luego el tipo **"Negocio"** (*Business*).
4. [ ] Portafolio comercial: puedes elegir *No conectar ahora*.
5. [ ] Termina con **Crear app** (te pedirá tu contraseña de Facebook).
6. [ ] Ve a *Configuración de la app → Básica*. Copia a `claves.txt` el **Identificador de la app** (APP_ID) y, con
      *Mostrar*, la **Clave secreta de la app** (APP_SECRET). Son temporales: solo se usan en el punto 2.4.

> La app queda en **modo desarrollo**, y está bien así: como eres administrador de la app y de la página, puedes publicar
> en tu página sin la revisión de Meta.

### 2.3 Token de usuario de corta duración
1. [ ] Abre el **Graph API Explorer**: <https://developers.facebook.com/tools/explorer/>.
2. [ ] A la derecha, en **Meta App**, elige `nostalgia-bot`.
3. [ ] En **User or Page**, elige *User Token*.
4. [ ] En **Permissions**, agrega uno por uno. El campo *Add a Permission* se cierra después de cada uno: vuelve a
      hacer clic en él para agregar el siguiente. Al final deben verse los 4 como etiquetas:
   - `pages_show_list`
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `read_insights`
   - (si tu página está en un portafolio comercial, también `business_management`)

   > **Si no aparecen en la lista** (solo salen `public_profile` o `email`): ve a developers.facebook.com/apps → tu app
   > → **Casos de uso** → *Administrar todo en tu página* → **Personalizar** → en *Permisos*, toca **Agregar** en los 4.
   > Luego recarga el Explorer y vuelve a elegir tu app.
5. [ ] Clic en **Generate Access Token**. Se abre una ventana de Facebook: **marca tu página** y acepta todos los permisos.
6. [ ] Copia el token que aparece arriba (empieza con `EAA...`). Es el **TOKEN_CORTO** y dura alrededor de 1 hora, así que haz
      el paso 2.4 enseguida.

### 2.4 Cambiarlo por un token largo
1. [ ] Arma esta URL reemplazando los 3 valores, pégala en el navegador y presiona Enter:
   ```
   https://graph.facebook.com/v23.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=TOKEN_CORTO
   ```
2. [ ] Vas a ver algo como `{"access_token":"EAA....","token_type":"bearer","expires_in":5183944}`. Copia ese
      `access_token`: es el **TOKEN_LARGO**.

### 2.5 Obtener el ID y el token de la página
1. [ ] Pega en el navegador (reemplazando TOKEN_LARGO):
   ```
   https://graph.facebook.com/v23.0/me/accounts?access_token=TOKEN_LARGO
   ```
2. [ ] Busca tu página en la respuesta:
   ```
   {"data":[{"access_token":"EAA...MUY_LARGO","category":"...","name":"Nostalgia Animada","id":"1234567890", ...}]}
   ```
3. [ ] Guarda en `claves.txt`:
   - `FB_PAGE_ID` = el valor de `"id"` (solo números)
   - `FB_PAGE_TOKEN` = el valor de `"access_token"` **de ese mismo bloque** (no el TOKEN_LARGO).

### 2.6 Verificar que no expira
1. [ ] Abre <https://developers.facebook.com/tools/debug/accesstoken/>, pega el `FB_PAGE_TOKEN` y haz clic en *Depurar*.
2. [ ] Revisa que diga **Tipo: Page**, **Vence: Nunca** (*Expires: Never*) y que en *Ámbitos* estén los permisos del 2.3.
3. [ ] Si dice que vence en 1 hora, usaste el token corto en el paso 2.5: repite el 2.4 y el 2.5.

> El token de página deja de funcionar si cambias la contraseña de Facebook, si quitas la app o si dejas de ser
> administrador. En ese caso repite los pasos 2.3 a 2.6 y actualiza el secret `FB_PAGE_TOKEN` (Paso 9).

---

## Paso 3: Clave de Gemini (5 min)

1. [ ] Entra a <https://aistudio.google.com/apikey> con tu cuenta de Google y acepta los términos.
2. [ ] **Create API key**. Si te pregunta, elige *Create API key in new project*.
3. [ ] Copia la clave (empieza con `AIza...`) en `claves.txt` como `GEMINI_API_KEY`.
4. [ ] **No actives la facturación** (*billing*) en ese proyecto: así siempre se queda en la capa gratuita, y si pasas el
      límite, el sistema espera y reintenta en vez de cobrarte.
5. [ ] Mira en AI Studio qué modelos *Flash* gratuitos hay. Si `gemini-3.8-flash` ya no aparece, anota el nombre del
      flash vigente para el Paso 7.

> En la capa gratuita, Google puede usar lo que envías para mejorar sus productos. Aquí solo se envían capítulos y textos
> de memes, nada personal.

---

## Paso 4: Cuenta de Imgflip (5 min)

1. [ ] Regístrate en <https://imgflip.com/signup> **con usuario y contraseña** (no con "Continuar con Google", porque la API
      necesita una contraseña).
2. [ ] Confirma el correo si te llega uno.
3. [ ] Guarda en `claves.txt`: `IMGFLIP_USER` (tu nombre de usuario, no el correo) y `IMGFLIP_PASS` (tu contraseña).

---

## Paso 5: Bot de Telegram (10 min)

1. [ ] En Telegram, busca **@BotFather** (con la palomita azul) y escribe `/newbot`.
2. [ ] Nombre del bot: por ejemplo `Nostalgia Avisos`. Usuario: algo que termine en `bot`, como `nostalgia_avisos_bot`.
3. [ ] BotFather te responde con un token como `7123456789:AAH...`. Guárdalo como `TELEGRAM_TOKEN`.
4. [ ] Busca tu bot por su usuario, ábrelo, toca **Iniciar** y mándale cualquier mensaje ("hola").
5. [ ] Abre en el navegador (reemplazando TOKEN):
   ```
   https://api.telegram.org/botTOKEN/getUpdates
   ```
6. [ ] Busca `"chat":{"id":123456789,...` y guarda ese número como `TELEGRAM_CHAT_ID`.
      Si la respuesta sale vacía (`"result":[]`), mándale otro mensaje al bot y recarga la página.

---

## Paso 6: Google Drive y rclone, la carpeta vigilada (25 min)

> **Forma fácil (recomendada):** primero pon tus series en `config.yaml` (Paso 7). Luego, en la carpeta del
> proyecto, haz clic derecho en `configurar_drive.ps1` → **Ejecutar con PowerShell**. El script instala rclone, abre
> el navegador para que des permiso a Drive, crea todas las carpetas y deja `RCLONE_CONF` copiado en el portapapeles.
> Si lo usas, sáltate los puntos 6.1 a 6.4.

### 6.1 Instalar rclone
1. [ ] Abre **PowerShell** (tecla Windows → escribe "PowerShell" → Enter) y ejecuta:
   ```
   winget install Rclone.Rclone
   ```
2. [ ] **Cierra y vuelve a abrir** PowerShell, y comprueba con `rclone version`.

### 6.2 Conectar tu Google Drive
Ejecuta `rclone config` y responde así:

| Pregunta | Respuesta |
|---|---|
| `e/n/d/r/c/s/q>` | `n` |
| `name>` | `drive` (exactamente así) |
| `Storage>` | escribe `drive` (Google Drive) |
| `client_id>` | Enter (vacío) |
| `client_secret>` | Enter (vacío) |
| `scope>` | `1` (acceso completo) |
| `service_account_file>` | Enter (vacío) |
| `Edit advanced config?` | `n` |
| `Use web browser to automatically authenticate?` | `y` → se abre el navegador → elige tu cuenta → **Permitir** |
| `Configure this as a Shared Drive?` | `n` |
| `Keep this "drive" remote?` | `y` |
| `e/n/d/r/c/s/q>` | `q` |

- [ ] Prueba con `rclone lsd drive:`: debe listar las carpetas de tu Drive.

> Si prefieres **OneDrive**: en `Storage>` escribe `onedrive`, llama al remote `drive` igualmente y elige *OneDrive Personal*.

### 6.3 Crear las carpetas
Ejecuta en PowerShell (una línea por serie de tu lista; los nombres tienen que coincidir **exactamente** con el Paso 7):
```
rclone mkdir "drive:Nostalgia/procesados"
rclone mkdir "drive:Nostalgia/errores"
rclone mkdir "drive:Nostalgia/pendientes"
rclone mkdir "drive:Nostalgia/entrada/Dragon Ball Z"
rclone mkdir "drive:Nostalgia/entrada/Hey Arnold"
rclone mkdir "drive:Nostalgia/entrada/Los Simpson"
rclone mkdir "drive:Nostalgia/entrada/Bob Esponja"
rclone mkdir "drive:Nostalgia/entrada/Los Padrinos Magicos"
```
- [ ] Comprueba en <https://drive.google.com> que existe `Nostalgia/` con esas subcarpetas.

### 6.4 Copiar la configuración de rclone
1. [ ] Ejecuta `rclone config file`. Te muestra la ruta, normalmente
      `C:\Users\marti\AppData\Roaming\rclone\rclone.conf`.
2. [ ] Ábrela con el Bloc de notas: `notepad "C:\Users\marti\AppData\Roaming\rclone\rclone.conf"`.
3. [ ] Copia **todo** el contenido (desde `[drive]` hasta la última línea con el token) y pégalo en `claves.txt` como
      `RCLONE_CONF`.

---

## Paso 7: Ajustar `config.yaml` (10 min)

Abre `C:\Users\marti\OneDrive\Documentos\FACEBOOK\config.yaml` en VS Code y revisa:

- [ ] `pagina.nombre`: el nombre de tu página (sale como marca de agua en los videos).
- [ ] `gemini.modelo`: cámbialo solo si en el Paso 3 viste que `gemini-3.8-flash` ya no existe.
- [ ] `horarios`: horas de los Reels y del video largo (hora de México). Ajústalas si quieres.
- [ ] `resumen.voz`: `es-MX-JorgeNeural` (hombre) o `es-MX-DaliaNeural` (mujer).
- [ ] `resumen.palabras_por_parte`: `[150, 200]` da Reels de ~60 a 80 s. No pases de 200: si la narración se pasa de
      90 s, el bot quita frases del medio (nunca el gancho del inicio ni el suspenso del final).
- [ ] `tarjetas.cierre_continua`: texto final de las partes intermedias ("Continúa en la parte 2…").
      `tarjetas.cierre`: texto final de la última parte y del video largo ("¿Te acordabas de este capítulo?").
- [ ] `aprobacion.activa`: déjalo en `true` para que nada se publique sin tu ✅. `enviar_videos: true` te manda cada
      Reel a Telegram para verlo antes de aprobar.
- [ ] `almacenamiento.remoto`: déjalo en `drive:Nostalgia` si seguiste el Paso 6 tal cual.
- [ ] `series`: una entrada por serie.
  - `carpeta`: el nombre **exacto** de la subcarpeta en `entrada/`.
  - `tvmaze`: el nombre con que aparece en <https://www.tvmaze.com>, normalmente el título original en inglés. Búscalo
    ahí para confirmarlo.
  - `activa`: `true` o `false`.

> Para agregar una serie después: crea su carpeta (`rclone mkdir "drive:Nostalgia/entrada/NOMBRE"` o desde la web de
> Drive), añádela en `config.yaml` y sube el cambio (Paso 8.4).

---

## Paso 8: Subir el proyecto a GitHub (30 min)

### 8.1 Cuenta e instalación de Git
1. [ ] Crea una cuenta en <https://github.com/signup> (si no tienes una).
2. [ ] En PowerShell: `winget install Git.Git`. Luego **cierra y vuelve a abrir** PowerShell y comprueba con `git --version`.
3. [ ] Configura tu identidad:
   ```
   git config --global user.name "Tu Nombre"
   git config --global user.email "martinetr244@gmail.com"
   ```

### 8.2 Crear el repositorio
1. [ ] <https://github.com/new>:
   - Nombre: por ejemplo `nostalgia-bot`.
   - Visibilidad: **Public**. Así los minutos de Actions son ilimitados, y las claves no se ven porque van como secrets.
   - **No** marques "Add a README" ni ningún otro archivo.
2. [ ] Clic en **Create repository** y copia la URL (`https://github.com/TU_USUARIO/nostalgia-bot.git`).

> Si quieres el repositorio **privado**, tienes 2000 minutos al mes. En ese caso cambia en
> `.github/workflows/resumenes.yml` la línea `cron: "*/30 * * * *"` por `cron: "0 */3 * * *"` (cada 3 horas), y en
> `.github/workflows/aprobaciones.yml` la línea `cron: "*/10 * * * *"` por `cron: "0 * * * *"` (cada hora).

### 8.3 Subir los archivos
En PowerShell:
```
cd "C:\Users\marti\OneDrive\Documentos\FACEBOOK"
git init
git add .
git status
```
- [ ] En la lista de `git status` **no** debe aparecer `.env` ni `claves.txt`. Si guardaste `claves.txt` en esta
      carpeta, muévelo a otra antes de seguir.

```
git commit -m "Inicio del proyecto"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/nostalgia-bot.git
git push -u origin main
```
- [ ] La primera vez se abre una ventana para iniciar sesión en GitHub: autoriza en el navegador.
- [ ] Recarga la página del repositorio: deben aparecer `src/`, `.github/`, `config.yaml`, etc.

### 8.4 Cómo subir cambios después
Cada vez que edites `config.yaml` u otro archivo:
```
cd "C:\Users\marti\OneDrive\Documentos\FACEBOOK"
git pull
git add .
git commit -m "Ajuste de config"
git push
```
(Ejecuta siempre `git pull` primero: el bot hace commits del registro de publicaciones en `data/`.)

---

## Paso 9: Cargar las claves (secrets) y permisos (10 min)

1. [ ] En tu repositorio: **Settings → Secrets and variables → Actions → New repository secret**.
2. [ ] Crea estos 8 secrets. El nombre va **exacto, en mayúsculas**, y el valor sin comillas ni espacios extra:

| Name | Secret |
|---|---|
| `FB_PAGE_ID` | id de la página (Paso 2.5) |
| `FB_PAGE_TOKEN` | token de página (Paso 2.5) |
| `GEMINI_API_KEY` | Paso 3 |
| `IMGFLIP_USER` | Paso 4 |
| `IMGFLIP_PASS` | Paso 4 |
| `TELEGRAM_TOKEN` | Paso 5 |
| `TELEGRAM_CHAT_ID` | Paso 5 |
| `RCLONE_CONF` | contenido completo de `rclone.conf` (Paso 6.4) |

3. [ ] **Settings → Actions → General**:
   - *Actions permissions*: **Allow all actions and reusable workflows**.
   - *Workflow permissions*: **Read and write permissions** → **Save**.
4. [ ] Pestaña **Actions** del repositorio: si aparece un botón *"I understand my workflows, go ahead and enable them"*,
      haz clic.
5. [ ] **Borra `claves.txt`** (y vacía la papelera). Las claves ya quedaron guardadas en GitHub.

---

## Paso 10: Pruebas de arranque (30–60 min, en este orden)

### 10.1 Meme de prueba
1. [ ] **Actions → Memes → Run workflow → Run workflow**.
2. [ ] Espera 1–2 minutos: el círculo debe ponerse en ✅ verde.
3. [ ] Abre tu página: debe aparecer el meme.
4. [ ] En el repositorio debe existir `data/memes.jsonl` con un commit de `nostalgia-bot`.

### 10.2 Capítulo de prueba
1. [ ] Sube un capítulo a `Nostalgia/entrada/<serie>/` desde <https://drive.google.com> (arrástralo). Nómbralo con su
      temporada y número, por ejemplo `Hey Arnold S02E03.mp4` (también sirve `2x03`). Para la prueba, mejor un capítulo
      corto (≤ 25 min).
2. [ ] Espera a que Drive termine de subirlo.
3. [ ] **Actions → Carpeta vigilada (resúmenes) → Run workflow**.
4. [ ] El job **revisar** debe decir `1 archivo(s) nuevo(s)`, y luego corre **procesar** (de 15 a 40 min).
5. [ ] Llegan a Telegram: `📝 Nuevo guion para revisar`, luego **cada Reel como video** (en calidad reducida, solo
      para revisar; a Facebook se sube en 1080p) con su texto, y al final un mensaje con 3 botones. Si dice "Se quitaron
      N frases", revisa que la parte se siga entendiendo; si no, toca 🔁.
6. [ ] Mira las partes: voz clara, subtítulos sincronizados, que cada parte (menos la última) termine en suspenso con
      "Continúa en la parte X", y la marca arriba. Lee el guion: si Gemini inventó un dato o un nombre está mal, toca
      **🔁 Regenerar**.
7. [ ] En Drive, el capítulo pasó a `Nostalgia/procesados/` y los videos están en `Nostalgia/pendientes/<id>/`.
8. [ ] Toca **✅ Aprobar y programar**. Para no esperar al cron (10 min), ve a **Actions → Aprobaciones (Telegram) →
      Run workflow**.
9. [ ] El mensaje de los botones cambia a `✅ Aprobado y programado:` con las fechas, y los botones desaparecen.
10. [ ] En **Meta Business Suite → Planificador** (<https://business.facebook.com>) aparecen los Reels y el video largo
      programados, y `Nostalgia/pendientes/<id>/` ya no existe.

> Los botones: **✅ Aprobar** programa todo en los próximos horarios libres. **🔁 Regenerar** devuelve el capítulo a
> `entrada/` y en ≤ 30 min te llega un guion nuevo. **🗑 Descartar** borra los videos; el capítulo queda en `procesados/`.
> El efecto no es inmediato: se aplica en la siguiente revisión (cada 10 min, más el retraso normal de GitHub).

### 10.3 Informe de recomendaciones
1. [ ] **Actions → Recomendaciones → Run workflow** (deja marcado *semanal*).
2. [ ] Llega a Telegram el informe con el siguiente capítulo por serie, las tendencias y las fechas. El ranking de series
      aparece una vez que haya publicaciones de más de 24 horas.

### 10.4 Confirmar que funciona solo
- [ ] Al día siguiente: hay memes publicados a las 11:00, 15:00 y 22:30 sin que hayas hecho nada.
      GitHub puede retrasar los cron de 5 a 30 minutos, y es normal.
- [ ] Los Reels programados se publicaron a su hora.

---

## Paso 11: Monetización (cuando la página tenga movimiento)

1. [ ] **Business Suite → Monetización** (o *Herramientas profesionales → Monetización* desde la página). Revisa en qué
      programas eres elegible (Content Monetization u otros) y qué te falta. Los requisitos cambian, así que míralos ahí.
2. [ ] Configura tu **cuenta de pago** y los datos fiscales cuando Meta te lo pida.
3. [ ] Afiliados: crea una cuenta en **Mercado Libre Afiliados** o **Amazon Afiliados** y pon enlaces a productos de las
      series en comentarios fijados.
4. [ ] Revisa **Business Suite → Calidad de la página** (o *Estado de la cuenta*) cada semana para detectar
      restricciones o reclamaciones de derechos.

---

## Rutina después del arranque (unos 15 min a la semana)

| Cuándo | Qué haces |
|---|---|
| Cuando llegue "📝 Nuevo guion para revisar" | Mira los Reels, lee el guion y toca ✅, 🔁 o 🗑 (2–3 min por capítulo) |
| Cuando Telegram avise "⏳ Quedan X días" | Sube 2 o 3 capítulos de las sugerencias a `entrada/<serie>/` |
| Domingo | Lee el informe de Telegram. Pausa en `config.yaml` las series que rinden poco y agrega las que son tendencia |
| Una vez a la semana | Revisa *Calidad de la página* y los mensajes en Business Suite |
| Si llega un "❌ Error" | Mira la sección de problemas comunes. El capítulo está en `errores/`: muévelo de nuevo a `entrada/` para reintentarlo |

Cada capítulo rinde 3 a 6 Reels (1 a 2 días con 3 horarios) más 1 video largo.

---

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Falta la variable de entorno X` | Falta un secret o tiene otro nombre | Paso 9: revisa el nombre exacto |
| `Graph API 190` / `Error validating access token` | Token vencido o inválido | Repite los pasos 2.3 a 2.6 y actualiza `FB_PAGE_TOKEN` |
| `Graph API 200` / `permission` | Falta un permiso en el token | Repite el 2.3 marcando todos los permisos y la página |
| Error en `video_reels` (`finish`) | Meta cambió algún parámetro de los Reels | Copia el error y pídeme ayuda para ajustar `src/fb.py` |
| `Imgflip: ...username/password` | Cuenta creada con Google o usuario mal escrito | Paso 4: crea una contraseña en Imgflip |
| Gemini `404 model not found` | El modelo fue retirado | Cambia `gemini.modelo` en `config.yaml` |
| Gemini `429` repetido | Límite de la capa gratuita | Espera; si pasa siempre, baja `partes_max` o procesa capítulos más cortos |
| `revisar` dice `0 archivo(s)` con un capítulo en la carpeta | Extensión no soportada, carpeta equivocada o remote mal nombrado | Revisa `extensiones` en `config.yaml` y que esté en `Nostalgia/entrada/<serie>/` |
| `rclone ... token expired` / `invalid_grant` | Se revocó el acceso de rclone a Drive | Ejecuta `rclone config reconnect drive:` y vuelve a copiar `rclone.conf` al secret |
| `Guardar estado` falla con `push rejected` | Activaste *Read and write* tarde | Paso 9.3 y vuelve a ejecutar el workflow |
| No llegan mensajes de Telegram | Nunca le escribiste al bot o el chat id está mal | Paso 5.4 a 5.6 |
| Los cron dejaron de correr | GitHub los pausa tras 60 días sin actividad | Pestaña Actions → elige el workflow → *Enable workflow* |
| Llegan reclamaciones de derechos | Rights Manager detectó la serie | Pon esa serie en `activa: false` |
| Toqué ✅ y no pasa nada | El cron aún no corre o GitHub lo retrasó | Espera 10–30 min o *Actions → Aprobaciones → Run workflow* |
| `ℹ️ ... ya se había resuelto antes` | Tocaste dos veces o la carpeta de `pendientes/` ya no existe | Nada que hacer |
| Llega el guion pero no los videos | Algún Reel pesa más de 50 MB (límite de los bots) | Aprueba igual, o revísalo en `Nostalgia/pendientes/<id>/` en Drive |
| `❌ Error con <id>` tras aprobar | Falló Facebook a mitad de camino | Corrige la causa (token, etc.) y toca ✅ otra vez: no duplica lo ya programado |
| `pendientes/` acumula carpetas | Guiones que nunca aprobaste ni descartaste | Tócales 🗑 o bórralas desde Drive |

---

## Resumen de cuentas creadas

| Servicio | Para qué | Dónde se administra |
|---|---|---|
| Página de Facebook | La página | business.facebook.com |
| Meta for Developers (`nostalgia-bot`) | Token de publicación | developers.facebook.com/apps |
| Google AI Studio | Gemini (resúmenes, memes, tendencias) | aistudio.google.com |
| Imgflip | Imágenes de memes | imgflip.com |
| Bot de Telegram | Avisos y recomendaciones | @BotFather |
| Google Drive + rclone | Carpeta vigilada | drive.google.com |
| GitHub | Donde corre todo | github.com/TU_USUARIO/nostalgia-bot |
