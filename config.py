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

# Logo específico de "Soporte TI" (el mono/mascota con audífonos) — se
# muestra arriba del listado de páginas en la barra lateral (st.logo, en
# app.py y en pages/1_Sistema_IT.py), arriba del título de la página pública,
# y en la pantalla de inicio de sesión del equipo de TI (ver auth.py).
LOGO_SOPORTE_PATH = os.path.join(BASE_DIR, "assets", "logo_soporte.png")

# Logos para la "Orden de Solicitud" en PDF (ver utils.orden_solicitud_pdf_bytes)
# — cada ticket lleva el logo de la empresa del solicitante (ver
# EMPRESAS_TICKET más abajo): Visión Digital usa el suyo, y Vitatrac GT y
# Vitatrac HN comparten el mismo logo de Vitatrac.
LOGO_ORDEN_VISION_DIGITAL_PATH = os.path.join(BASE_DIR, "assets", "logo_orden_vision_digital.jpg")
LOGO_ORDEN_VITATRAC_PATH = os.path.join(BASE_DIR, "assets", "logo_orden_vitatrac.png")

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
CATEGORIAS_TICKET = ["Soporte Técnico", "Soporte Oracle"]
CATEGORIA_DESCRIPCION = {
    "Soporte Técnico": "Equipo de cómputo, impresoras, redes, VPN, periféricos, accesos, contraseñas, correo.",
    "Soporte Oracle": "Todo lo relacionado con el sistema Oracle: accesos, errores, reportes y módulos.",
}

# El solicitante primero elige de qué empresa es, y según esa elección se le
# ofrece la lista de tiendas/áreas de ESA empresa (con opción de escribir una
# distinta si no está en la lista — mismo patrón que "Responsable" en Minutas
# de Tienda, de la plataforma comercial). Edítalas aquí si cambia la lista de
# empresas o de tiendas/áreas de alguna de ellas.
EMPRESAS_TICKET = [EMPRESA_NOMBRE, "Vitatrac GT", "Vitatrac HN"]

AREAS_POR_EMPRESA = {
    EMPRESA_NOMBRE: [
        "Cayalá", "Vista Hermosa", "Majadas", "CAES",
        "Oficinas Centrales / Administración", "Planta / Producción", "Logística",
    ],
    "Vitatrac GT": [
        "Aguilar Batres", "Montserrat", "Roosevelt", "San Cristóbal", "Obelisco", "Hincapié",
        "CAES", "Escuintla", "Santa Lucía", "Mazatenango", "Xela 1", "Xela 2", "Huehuetenango",
        "Quiché", "Cobán", "Puerto Barrios", "Teculután", "Compras", "Contabilidad", "Créditos",
        "Logística", "RRHH", "Mercadeo", "Venta Externa", "Mayoreo",
    ],
    "Vitatrac HN": [
        "San Pedro Sula", "Tegucigalpa", "Bodega", "Contabilidad", "RRHH", "Créditos", "Mercadeo",
        "Mayoreo", "Venta Externa", "Logística", "Compras",
    ],
}
ESCRIBIR_AREA_NUEVA = "✍️ Otra (escribir)"

# Qué logo lleva la Orden de Solicitud en PDF según la empresa del ticket.
LOGO_POR_EMPRESA = {
    EMPRESA_NOMBRE: LOGO_ORDEN_VISION_DIGITAL_PATH,
    "Vitatrac GT": LOGO_ORDEN_VITATRAC_PATH,
    "Vitatrac HN": LOGO_ORDEN_VITATRAC_PATH,
}

# Flujo del ticket: 4 columnas del tablero interno (ver pages/1_Sistema_IT.py).
# Ya no existe un paso manual a "Cerrado": en cuanto un ticket lleva un día
# completo como "Resuelto" (es decir, al cambiar de día calendario), sale
# solo del tablero y pasa a la sección "Historial" — ver
# database.ticket_es_historico().
ESTADOS_TICKET = ["Nuevo", "Asignado", "En proceso", "Resuelto"]
TICKET_SIGUIENTE_ESTADO = {
    "Nuevo": "Asignado",
    "Asignado": "En proceso",
    "En proceso": "Resuelto",
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

# Nombres de mes en español, para los selectores "Mes" de los filtros por
# mes/año (Historial, Dashboard) — ver pages/1_Sistema_IT.py y
# pages/2_Dashboard.py.
MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

# ---------------------------------------------------------------------------
# Urgencia: el propio solicitante la marca al reportar el problema (ver
# app.py) y el equipo de TI la ve reflejada como color/ícono en cada tarjeta
# del tablero y del historial, en la Orden de Solicitud en PDF, en "Consultar
# un ticket" y en el aviso por correo (ver pages/1_Sistema_IT.py, utils.py,
# app.py y database.enviar_avisos_ticket_nuevo). "Emergencia" además
# parpadea en el tablero (ver el CSS en auth.py) para que salte a la vista
# de inmediato.
URGENCIAS_TICKET = ["Normal", "Urge", "Crítico", "Emergencia"]
URGENCIA_DEFECTO = "Normal"
URGENCIA_EMOJI = {
    "Normal": "⚫",
    "Urge": "🟡",
    "Crítico": "🔴",
    "Emergencia": "🚨",
}
URGENCIA_COLOR = {
    "Normal": "#111827",   # negro
    "Urge": "#b45309",     # amarillo/ámbar (más legible que un amarillo puro sobre fondo blanco)
    "Crítico": "#dc2626",  # rojo
    "Emergencia": "#dc2626",  # rojo, con el ícono parpadeando (ver utils.urgencia_badge_html)
}
URGENCIA_DESCRIPCION = {
    "Normal": "Puede esperar su turno normal.",
    "Urge": "Necesita atención pronto, no es una emergencia pero no debería esperar mucho.",
    "Crítico": "Te bloquea el trabajo — atenderlo lo antes posible.",
    "Emergencia": "Situación urgente que necesita atención inmediata (ej. un sistema caído para todos).",
}
