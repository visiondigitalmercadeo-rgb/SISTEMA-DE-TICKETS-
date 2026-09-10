"""Utilidades chicas: convertir una foto/captura adjunta a base64 con un
límite de tamaño seguro (mismo concepto que plataforma_ventas: Firestore
tiene un límite duro de 1 MiB por documento), y generar el PDF de la 'Orden
de Solicitud' de un ticket (mismo patrón de plataforma_ventas.utils, que ya
genera PDFs de minutas/pedidos/diseños con fpdf2)."""

import base64

from fpdf import FPDF

from config import EMPRESA_NOMBRE, LOGO_ORDEN_VISION_DIGITAL_PATH, LOGO_POR_EMPRESA


def formatear_horas(horas):
    """Convierte un número de horas a un texto corto y legible — en horas
    si es menos de 2 días, o en días con un decimal si es más (para no
    mostrar '620 h' cuando es más claro decir '25.8 d'). Usado en los KPIs
    del Tablero y del Dashboard (ver pages/1_Sistema_IT.py y
    pages/2_Dashboard.py)."""
    if horas is None:
        return "—"
    if horas < 48:
        return f"{horas:.0f} h"
    return f"{horas / 24:.1f} d"


def archivo_a_b64(archivo_subido, max_bytes: int):
    """Convierte un archivo de st.file_uploader a base64. Retorna
    (b64_str, nombre, tipo) o lanza ValueError si pesa más de lo permitido
    (se revisa el tamaño ANTES de codificar, para no gastar memoria de más)."""
    crudo = archivo_subido.getvalue()
    if len(crudo) > max_bytes:
        limite_kb = max_bytes // 1000
        raise ValueError(
            f"Ese archivo pesa demasiado (máximo ~{limite_kb} KB). Comprime la imagen o sube una más liviana."
        )
    b64 = base64.b64encode(crudo).decode("ascii")
    return b64, archivo_subido.name, archivo_subido.type


_PDF_SUSTITUCIONES = {
    "—": "-", "–": "-", "…": "...", "•": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
}


def _pdf_safe(texto):
    """Los PDFs con fuentes estándar (Helvetica) solo soportan Latin-1 (los
    acentos y la 'ñ' del español sí entran ahí, así que esos se ven bien).
    Primero cambia algunos símbolos comunes por su equivalente en Latin-1
    (rayas, comillas curvas, puntos suspensivos); lo que sigue sin entrar
    (sobre todo emojis) simplemente se omite, en vez de dejar un '?' feo."""
    texto = str(texto)
    for buscado, reemplazo in _PDF_SUSTITUCIONES.items():
        texto = texto.replace(buscado, reemplazo)
    return texto.encode("latin-1", "ignore").decode("latin-1")


def _fecha_corta(iso_txt):
    if not iso_txt or len(iso_txt) < 10:
        return "—"
    return f"{iso_txt[8:10]}/{iso_txt[5:7]}/{iso_txt[0:4]}"


def orden_solicitud_pdf_bytes(ticket: dict) -> bytes:
    """Genera la 'Orden de Solicitud' en PDF de un ticket — se manda como
    adjunto al crear el ticket (al solicitante y al personal de soporte de
    esa categoría) y también cuando se asigna a un técnico en particular
    (ver database.enviar_orden_ticket). Lleva el logo de la empresa del
    solicitante: Visión Digital usa el suyo, y Vitatrac GT/HN comparten el
    logo de Vitatrac (ver config.LOGO_POR_EMPRESA). Se genera siempre al
    vuelo a partir de lo que ya está guardado en Firestore — no se guarda
    el PDF en ningún lado."""
    pdf = FPDF(format="Letter")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # -- Encabezado: logo de la empresa a la izquierda, caja "ORDEN DE
    #    SOLICITUD No." a la derecha (mismo estilo que Minutas/Pedidos). --
    logo_path = LOGO_POR_EMPRESA.get(ticket.get("empresa"), LOGO_ORDEN_VISION_DIGITAL_PATH)
    try:
        pdf.image(logo_path, x=10, y=10, w=50)
    except Exception:
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_xy(10, 14)
        pdf.cell(70, 8, _pdf_safe(ticket.get("empresa") or EMPRESA_NOMBRE))

    caja_x, caja_w = 130, 72
    pdf.set_fill_color(20, 20, 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_xy(caja_x, 12)
    pdf.cell(caja_w, 8, _pdf_safe("ORDEN DE SOLICITUD No."), border=0, align="C", fill=True)

    numero = ticket.get("numero")
    texto_numero = f"TI-{numero:04d}" if isinstance(numero, int) else "TI-____"
    pdf.set_text_color(0, 0, 0)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_xy(caja_x, 20)
    pdf.cell(caja_w, 10, _pdf_safe(texto_numero), border=1, align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.set_xy(caja_x, 32)
    pdf.cell(caja_w, 5, _pdf_safe(ticket.get("categoria") or "—"), align="C")
    pdf.set_text_color(0, 0, 0)

    pdf.set_y(48)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # "contacto" es el campo viejo, de antes de separar correo y teléfono —
    # se usa como respaldo solo para tickets creados antes de ese cambio.
    campos = [
        ("Empresa", ticket.get("empresa") or "—"),
        ("Tienda / área", ticket.get("area") or "—"),
        ("Fecha de solicitud", _fecha_corta(ticket.get("creado_en"))),
        ("Solicitante", ticket.get("nombre_solicitante") or "—"),
        ("Correo", ticket.get("correo") or ticket.get("contacto") or "—"),
        ("Teléfono", ticket.get("telefono") or "—"),
        ("Estado actual", ticket.get("estado") or "—"),
        ("Asignado a", ticket.get("asignado_a_nombre") or "Sin asignar todavía"),
    ]
    for etiqueta, valor in campos:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _pdf_safe(f"{etiqueta}:"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 7, _pdf_safe(valor))
        pdf.ln(1)

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _pdf_safe("Problema reportado:"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, _pdf_safe(ticket.get("descripcion") or "—"))

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, _pdf_safe(f"Documento generado automáticamente por Sistema IT — {EMPRESA_NOMBRE}."))

    return bytes(pdf.output())
