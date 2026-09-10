"""Configuración global de Soporte TI — Visión Digital.

Este es un sistema APARTE de la plataforma comercial (plataforma_ventas):
tiene su propio repositorio, su propio despliegue en Streamlit Cloud y su
propio login para el equipo de TI. Pero comparte el MISMO proyecto de
Firebase (mismas credenciales en Streamlit Cloud) — solo usa colecciones
nuevas, con el prefijo "it_", para no mezclarse nunca con los datos
comerciales (ver database.py).
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Marca
# ---------------------------------------------------------------------------
EMPRESA_NOMBRE = "Visión Digital"
LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo.png")
FAVICON_PATH = os.path.join(BASE_DIR, "assets", "favicon.png")

# URL pública de esta app — se actualiza aquí en cuanto Steven la despliegue
# en Streamlit Cloud y tenga la URL definitiva (se usa solo para armar el
# texto de "ver más" en algún aviso futuro; hoy no es indispensable).
APP_URL = "https://cambiar-por-la-url-real.streamlit.app"

# ---------------------------------------------------------------------------
# Tickets: categoría, a quién se le pregunta el requerimiento pidió Steven
# que el propio solicitante marque de una vez si es "Soporte Técnico" o
# "Soporte de Sistema" (ver app.py) — el equipo de TI puede reclasificarlo
# después desde el panel si el solicitante se equivocó.
# ---------------------------------------------------------------------------
CATEGORIAS_TICKET = ["Soporte Técnico", "Soporte de Sistema"]
CATEGORIA_DESCRIPCION = {
    "Soporte Técnico": "Equipo de cómputo, impresoras, redes, VPN, periféricos.",
    "Soporte de Sistema": "Aplicaciones, accesos y contraseñas, sistemas internos, Oracle, correo.",
}

# Tiendas/áreas conocidas, para que el solicitante elija rápido en vez de
# escribir — con opción de escribir una distinta si no está en la lista
# (mismo patrón que "Responsable" en Minutas de Tienda, de la plataforma
# comercial). Edítala aquí si cambia la lista de tiendas/áreas de la empresa.
AREAS = [
    "Cayalá", "Vista Hermosa", "Majadas", "CAES",
    "Oficinas Centrales / Administración", "Planta / Producción", "Logística",
]
ESCRIBIR_AREA_NUEVA = "✍️ Otra (escribir)"

# Flujo del ticket: 5 columnas del tablero interno (ver pages/1_Panel_TI.py).
ESTADOS_TICKET = ["Nuevo", "Asignado", "En proceso", "Resuelto", "Cerrado"]
TICKET_SIGUIENTE_ESTADO = {
    "Nuevo": "Asignado",
    "Asignado": "En proceso",
    "En proceso": "Resuelto",
    "Resuelto": "Cerrado",
}
ESTADO_EMOJI = {
    "Nuevo": "🆕", "Asignado": "👤", "En proceso": "🔧", "Resuelto": "✅", "Cerrado": "🔒",
}

# Foto/captura adjunta al reportar el problema — se guarda en base64 dentro
# del propio documento de Firestore (como el resto de adjuntos chicos de la
# plataforma comercial), con un límite bajo a propósito: Firestore tiene un
# límite duro de 1 MiB por documento, y el ticket ya lleva descripción +
# historial de seguimiento en el mismo documento.
TICKET_FOTO_MAX_BYTES = 350_000  # ~350 KB
