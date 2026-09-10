# Soporte TI — Visión Digital

Sistema de tickets de soporte técnico y de sistemas, separado de la plataforma comercial. Un empleado entra a un link público (sin usuario ni contraseña), reporta su problema, y el equipo de TI le da seguimiento desde un panel interno con su propio login.

## Qué trae

- **`app.py`** — la página pública (el link que compartes con todos los empleados). Tiene dos pestañas: "Reportar un problema" (pide nombre, correo, teléfono y **urgencia**, ver más abajo — todos obligatorios; la foto/captura adjunta es opcional, hasta ~600 KB) y "Consultar un ticket" (con el número que les da al enviar el suyo — desde ahí también pueden descargar su Orden de Solicitud en PDF).
- **`pages/1_🛠️_Sistema_IT.py`** — el panel interno del equipo de TI (en la barra lateral aparece como "🛠️ Sistema IT", con su propio ícono), con su propio login y estas pestañas:
  - **📋 Tablero**: arriba de todo, antes del filtro, unos **KPIs** — cuántos tickets van en el mes (total y por categoría), y cuánto tiempo lleva ahora mismo cada ticket sentado en su columna actual (promedio por columna, para detectar dónde se están atascando; ya no cuenta ahí los tickets que se archivaron a Historial). Debajo, el tablero: Nuevo → Asignado → En proceso → Resuelto. Cada tarjeta muestra su **chip de urgencia** (ver más abajo) junto al número de ticket. Ya no existe un paso manual a "Cerrado" — en cuanto un ticket lleva un día calendario completo como "Resuelto" (es decir, el mismo día que se resuelve todavía se ve en el tablero; al cambiar de día), sale solo del tablero y pasa a la pestaña Historial, sin eliminarse. Cada tarjeta también tiene un botón para descargar la Orden de Solicitud en PDF, y (solo para administradores) uno para eliminar el ticket por completo, con casilla de confirmación. La primera vez que alguien entra ahí, como todavía no hay ningún técnico registrado, la misma pantalla deja crear la primera cuenta (que queda como administrador del panel).
  - **🗂️ Historial**: la ven todos (técnicos y administradores). Lista de los tickets ya archivados (ver arriba, también con su chip de urgencia), filtrable por tipo (Soporte Técnico / Soporte Oracle), con un KPI arriba de "cuántos se cerraron por empresa" para el mes y año que elijas con los selectores de Mes/Año.
- **`pages/2_📊_Dashboard.py`** — página nueva (aparece como "📊 Dashboard" en la barra lateral, con su propio ícono), **solo para administradores**. Muestra los KPIs de todo el sistema — tickets creados, cerrados y el tiempo promedio de resolución — filtrables por **Mes**, **Año**, **Tipo** de solicitud (Soporte Técnico / Soporte Oracle) y **Empresa**. Cuando dejas el filtro de Tipo o Empresa en "Todos"/"Todas", además desglosa los números por cada categoría o cada empresa por separado, para comparar de un vistazo.
- **`pages/3_🔐_Administrador.py`** — página **independiente** (antes era una pestaña dentro de "Sistema IT"; aparece como "🔐 Administrador" en la barra lateral, con su propio ícono), también solo para administradores. Muestra al equipo de TI como una **lista compacta** (nombre, si es admin, activo/desactivado) con un botón "✏️ Editar" por persona — al hacer clic ahí se abre el detalle completo de esa persona (nombre/usuario/correo, restablecer contraseña, categorías que atiende, subir/bajar de administrador, activar/desactivar, eliminar), con un botón "← Volver a la lista" para regresar. Así no hay que hacer scroll entre los formularios de todo el equipo para editar a una sola persona. El sistema nunca deja quitarle el admin, desactivar ni eliminar al último administrador activo que quede, para que nadie se quede sin poder entrar a administrar el equipo. Más abajo en esa misma página están los **📱 Códigos QR de acceso por empresa** (ver la sección de abajo) y, al final, los **✉️ Correos de aviso por categoría** (ver más abajo).

  **Hay dos formas de agregar más administradores:** (1) en "➕ Agregar técnico o administrador", marca la casilla "🔑 Administrador del panel" al crear la cuenta nueva, o (2) si la persona ya tiene cuenta como técnico, entra a su fila → pestaña "⚙️ Permisos" → "⬆️ Hacer administrador". No hay límite de cuántos administradores puede haber.
- **`utils.py`** — genera la **Orden de Solicitud en PDF** de cada ticket (ver más abajo), con `fpdf2`.
- **`database.py`** — usa el **mismo proyecto de Firebase** que ya tienes conectado en la plataforma comercial (mismas credenciales), pero en colecciones nuevas (con el prefijo `it_`) para que nunca se mezclen los datos.

**Nota sobre "Dashboard" y "Administrador" en la barra lateral:** cualquier técnico (no solo los administradores) va a **ver listadas** esas dos páginas en su barra lateral, junto con "Sistema IT" — Streamlit muestra ahí todas las páginas que existen, no las esconde según el rol. Pero si un técnico sin permisos de administrador hace clic en cualquiera de las dos, lo que ve es un mensaje de "esta sección es solo para administradores", nunca el contenido. Es decir: la protección real está adentro de la página, no en que aparezca o no en el menú.

## 🚦 Urgencia de cada ticket

Al reportar un problema, el solicitante también marca qué tan urgente es:

| Urgencia | Color/ícono | Significado |
|---|---|---|
| **Normal** | ⚫ negro | Puede esperar su turno normal. |
| **Urge** | 🟡 amarillo | Necesita atención pronto, no es una emergencia. |
| **Crítico** | 🔴 rojo | Le bloquea el trabajo — atenderlo lo antes posible. |
| **Emergencia** | 🚨 rojo, parpadeando | Situación urgente que necesita atención inmediata (ej. un sistema caído para todos). |

Esa urgencia se ve reflejada como un chip de color en cada tarjeta del Tablero y del Historial (Sistema IT), en "Consultar un ticket" (app.py) y en la Orden de Solicitud en PDF. Además, si el solicitante marca **Crítico** o **Emergencia**, el correo de aviso al personal de soporte (ver la sección de abajo) sale marcado en el asunto para que no se pierda entre el resto de la bandeja de entrada.

## 📄 Orden de Solicitud en PDF

Cada ticket tiene su propia "Orden de Solicitud" en PDF, generada al vuelo (no se guarda en ningún lado — se arma de nuevo cada vez que se necesita) con los datos del ticket: empresa, tienda/área, fecha, solicitante, estado, a quién está asignado y la descripción del problema.

El logo que lleva depende de la empresa del ticket:
- **Visión Digital** → su logo (`assets/logo_orden_vision_digital.jpg`).
- **Vitatrac GT** y **Vitatrac HN** → el mismo logo de Vitatrac (`assets/logo_orden_vitatrac.png`).

Esta orden se manda por correo automáticamente en dos momentos:
1. **Al crear el ticket** — al personal de soporte de esa categoría y, si dejó correo válido, al solicitante (ver la siguiente sección).
2. **Al asignarlo a un técnico** — se le manda de nuevo, esta vez directo al correo de esa persona (el que le hayas puesto en Administrador → editar su perfil). Si ese técnico no tiene correo guardado, simplemente no se le manda nada a él (no truena, y el ticket se asigna igual).

## ✉️ Avisos por correo cuando entra un ticket nuevo

Cada vez que alguien reporta un problema, el sistema manda automáticamente (con la Orden de Solicitud en PDF adjunta):

1. Un correo al **personal de soporte** — a la lista de correos que configures en Administrador → "✉️ Correos de aviso por categoría", una lista para tickets de **Soporte Técnico** y otra para **Soporte Oracle** (puede ser la misma gente en ambas, o gente distinta — tú decides).
2. Un correo de confirmación al **solicitante**, con el correo que dejó en el campo "Correo electrónico" del formulario (es obligatorio y se valida que tenga formato de correo antes de guardar el ticket, así que siempre le llega).

Para que esto funcione, hay que conectar una cuenta de Gmail que mande los correos (es la MISMA cuenta que ya usa la plataforma comercial para las Minutas de Tienda — si ya la configuraste allá, es copiar y pegar el mismo bloque):

1. En **Settings → Secrets** de esta app (Soporte TI) en Streamlit Cloud, agrega (o pega, si ya la tienes en la otra app):
   ```
   [gmail_notificaciones]
   usuario = "correo@tudominio.com"
   app_password = "xxxx xxxx xxxx xxxx"
   ```
   (`app_password` es una "contraseña de aplicación" de Gmail, no la contraseña normal de la cuenta — se genera desde la configuración de seguridad de esa cuenta de Google.)
2. Dale "Save" y reinicia la app.
3. Entra a Administrador → "✉️ Correos de aviso por categoría" y guarda a quién avisar en cada categoría.

Mientras esto no esté configurado, los tickets se siguen guardando normal — simplemente no se manda ningún correo.

## 📱 Códigos QR de acceso por empresa

En Administrador hay una sección para generar un **código QR por cada empresa** (Visión Digital, Vitatrac GT, Vitatrac HN). Al escanearlo, el solicitante llega directo a la pestaña "Reportar un problema" con su empresa ya seleccionada — no tiene que escribir el link a mano ni elegir su empresa. Puedes imprimirlo o pegarlo (por ejemplo, en cada tienda/oficina).

Para usarlo:

1. Entra a Administrador → "📱 Código QR de acceso por empresa" y pega ahí el **link público** de esta app (el mismo que ya compartes para reportar problemas — Streamlit te lo da al desplegar, algo como `https://tu-app.streamlit.app`) y dale "Guardar link". Solo hay que hacerlo una vez; queda guardado para todos.
2. En cuanto lo guardes, van a aparecer un código QR y su link por cada empresa, cada uno con un botón para descargarlo como imagen PNG.

Si el link público de la app cambia en algún momento (por ejemplo, si mueves el despliegue a otra cuenta de Streamlit Cloud), solo hay que volver a esta sección y guardar el nuevo link — los QR viejos que ya imprimiste dejarían de funcionar, así que tendrías que reimprimirlos.

## Cómo desplegarlo (primera vez)

1. **Crea un repositorio nuevo en GitHub** (por ejemplo `soporte-ti-vision-digital`), separado del repositorio de la plataforma comercial.
2. Sube ahí **todos** estos archivos y carpetas, manteniendo la misma estructura (ojo: `pages/` y `assets/` son carpetas, no archivos sueltos):
   - `app.py`
   - `auth.py`
   - `database.py`
   - `config.py`
   - `utils.py`
   - `fake_firestore.py`
   - `requirements.txt`
   - `pages/1_🛠️_Sistema_IT.py`
   - `pages/2_📊_Dashboard.py`
   - `pages/3_🔐_Administrador.py`
   - `assets/logo.png`
   - `assets/logo_soporte.png`
   - `assets/logo_orden_vision_digital.jpg`
   - `assets/logo_orden_vitatrac.png`
   - `assets/favicon.png`
3. Entra a [share.streamlit.io](https://share.streamlit.io) (donde ya tienes la plataforma comercial) y crea una **app nueva**, apuntando al repositorio que acabas de crear, con `app.py` como archivo principal.
4. En **Settings → Secrets** de esta app nueva, pega el mismo bloque `[firebase]` que ya tienes configurado en la app de la plataforma comercial (cópialo tal cual de ahí — es el mismo proyecto de Firebase, solo lo está usando una app más). Si algún día quieres separar los proyectos de Firebase, avísame y lo migramos.
5. Dale "Deploy". En un par de minutos tendrás dos links:
   - El link principal (raíz) de la app — **ese es el que compartes con todos los empleados** para reportar problemas (por correo, WhatsApp, o hasta un QR si quieres).
   - Desde el menú lateral de esa misma app, el enlace a "Sistema IT" — **ese es el que usa el equipo de soporte** para atender los tickets (con su login).

## Primer uso

1. Comparte el link principal con un par de personas para probar que puedan reportar un ticket sin problema.
2. Entra tú (o quien vaya a liderar el equipo de TI) al link de "Sistema IT" y crea la primera cuenta — queda como administrador y desde ahí puedes agregar al resto de tus técnicos.
3. Reporta un ticket de prueba desde el link público y confirma que aparece en la columna "Nuevo" del panel.

## Actualizaciones futuras

Igual que con la plataforma comercial: cuando yo te entregue un archivo actualizado, lo reemplazas completo en GitHub (con "Commit changes") y reinicias esta app desde "Manage app" → "Reboot" en Streamlit Cloud.

**Importante — esta vez el panel interno cambió de nombre de archivo** (de `pages/1_Panel_TI.py` a `pages/1_Sistema_IT.py`, para que en la barra lateral se vea "Sistema IT" en vez de "Panel TI"). Reemplazar el contenido de `1_Panel_TI.py` NO es suficiente — hay que **borrar** `pages/1_Panel_TI.py` de GitHub y **subir** `pages/1_Sistema_IT.py` como un archivo nuevo; si dejas los dos, te van a aparecer las dos pestañas duplicadas en la barra lateral.

**Importante — `requirements.txt` también cambió otra vez** (ahora se agregó `qrcode`, la librería que genera los códigos QR de acceso por empresa — antes ya se había agregado `fpdf2`, la de la Orden de Solicitud en PDF). Reemplázalo también en GitHub — si no, la sección de códigos QR de Administrador va a avisar que falta instalarla. Este "Reboot" en particular puede tardar un poquito más de lo normal porque Streamlit Cloud tiene que instalar la librería nueva.

**Importante — esta vez hay dos páginas nuevas.** "Administrador" salió de adentro de "Sistema IT" y ahora es su propio archivo, y se agregó "Dashboard". Esto quiere decir que además de reemplazar los archivos que ya tenías, hay que **subir dos archivos nuevos** a la carpeta `pages/` de GitHub (con "Add file" → "Upload files", igual que la primera vez):
- `pages/2_📊_Dashboard.py`
- `pages/3_🔐_Administrador.py`

Si solo reemplazas `pages/1_🛠️_Sistema_IT.py` y no subes estos dos, no vas a tener errores, pero tampoco vas a ver "Dashboard" ni "Administrador" en la barra lateral (esa pestaña de Administrador ya no existe adentro de Sistema IT).

**El logo de la barra lateral** (el que está encima del menú de páginas) ahora se ve más grande — no cambia ningún archivo adicional a los que ya ibas a reemplazar, es parte del mismo `auth.py`.

**Importante — los 3 archivos de `pages/` volvieron a cambiar de nombre** (esta vez para agregarles un ícono en el menú, ver la sección de arriba):
- `pages/1_Sistema_IT.py` → `pages/1_🛠️_Sistema_IT.py`
- `pages/2_Dashboard.py` → `pages/2_📊_Dashboard.py`
- `pages/3_Administrador.py` → `pages/3_🔐_Administrador.py`

Igual que la vez pasada que renombramos "Panel TI" a "Sistema IT": reemplazar el CONTENIDO de los archivos viejos no alcanza — hay que **borrar los 3 archivos viejos** de la carpeta `pages/` en GitHub y **subir los 3 nuevos** (con esos nombres exactos, íconos incluidos) como archivos nuevos. Si dejas los viejos y los nuevos juntos, vas a ver las páginas duplicadas en la barra lateral. Para escribir el emoji en el nombre al subir el archivo en GitHub, lo más fácil es copiar y pegar el nombre completo (con el emoji) tal cual aparece arriba, en vez de escribirlo a mano.

**El chip de urgencia** (Normal/Urge/Crítico/Emergencia, ver la sección de arriba) no necesita ningún archivo ni librería nueva — ya viene incluido en `app.py`, `database.py`, `utils.py` y `pages/1_🛠️_Sistema_IT.py`.

**La lista compacta de Administrador y el límite más alto de la foto adjunta** (~600 KB, antes ~350 KB) tampoco necesitan ningún archivo ni librería nueva — solo reemplazar `pages/3_🔐_Administrador.py`, `config.py` y `app.py` como de costumbre.
