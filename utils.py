"""Utilidades chicas: convertir una foto/captura adjunta a base64 con un
límite de tamaño seguro (mismo concepto que plataforma_ventas: Firestore
tiene un límite duro de 1 MiB por documento), generar el PDF de la 'Orden
de Solicitud' de un ticket (mismo patrón de plataforma_ventas.utils, que ya
genera PDFs de minutas/pedidos/diseños con fpdf2), y generar el reporte de
KPIs del Dashboard en Excel/PDF (ver informe_kpis_excel_bytes /
informe_kpis_pdf_bytes, usados por pages/2_Dashboard.py)."""

import base64

from fpdf import FPDF

from config import (
    CATEGORIAS_TICKET, EMPRESA_NOMBRE, EMPRESAS_TICKET, ESTADOS_TICKET, ESTADO_EMOJI,
    LOGO_ORDEN_VISION_DIGITAL_PATH, LOGO_POR_EMPRESA, URGENCIA_COLOR, URGENCIA_DEFECTO,
    URGENCIA_EMOJI,
)


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


def generar_qr_png(texto: str):
    """Genera un código QR (en PNG, como bytes) para 'texto' — se usa para
    los códigos QR de acceso por empresa en Administrador (ver
    pages/3_Administrador.py), donde 'texto' es el link público de la app
    con la empresa ya elegida (?empresa=...). Devuelve None si la librería
    'qrcode' no está instalada (por ejemplo, si todavía no se actualizó
    requirements.txt en el despliegue) para que la página lo avise en vez
    de tronar."""
    try:
        import io
        import qrcode
    except ImportError:
        return None
    imagen = qrcode.make(texto, box_size=8, border=2)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return buffer.getvalue()


def urgencia_badge_html(urgencia: str) -> str:
    """Chip de HTML (color + ícono) para el nivel de urgencia de un ticket —
    se usa en las tarjetas del Tablero y del Historial (ver
    pages/1_Sistema_IT.py) y en 'Consultar un ticket' (ver app.py). Requiere
    que la página ya haya llamado a auth.mostrar_logo_sidebar() (o cualquier
    otra que inyecte el CSS global), de donde sale la animación de
    parpadeo para 'Emergencia'. Se usa siempre con unsafe_allow_html=True —
    el texto viene solo de config.URGENCIA_* (fijo, nunca de lo que escribe
    el solicitante), así que es seguro."""
    color = URGENCIA_COLOR.get(urgencia, URGENCIA_COLOR[URGENCIA_DEFECTO])
    emoji = URGENCIA_EMOJI.get(urgencia, URGENCIA_EMOJI[URGENCIA_DEFECTO])
    clase_extra = " urgencia-parpadea" if urgencia == "Emergencia" else ""
    return (
        f'<span class="urgencia-chip{clase_extra}" style="'
        f"display:inline-block;padding:2px 10px;border-radius:999px;"
        f"background:{color}1a;color:{color};border:1px solid {color}66;"
        f'font-weight:600;font-size:0.85rem;">{emoji} {urgencia or URGENCIA_DEFECTO}</span>'
    )


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
        ("Urgencia", ticket.get("urgencia") or URGENCIA_DEFECTO),
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


# ---------------------------------------------------------------------------
# Reporte de KPIs del Dashboard (Excel y PDF ejecutivo) — ver
# pages/2_Dashboard.py, botones "📥 Descargar este reporte". Ambas funciones
# reciben:
#   - periodo_texto: p.ej. "Agosto 2026" (el mes/año que se filtró en el
#     Dashboard).
#   - filtros_texto: p.ej. "Tipo: Soporte Técnico · Empresa: Vitatrac GT", o
#     "Todos los tipos y empresas" si no se filtró nada.
#   - kpis: el dict que devuelve database.calcular_kpis_dashboard (ya con el
#     mes/año/tipo/empresa elegidos en el Dashboard aplicados).
#   - kpis_tablero: el dict que devuelve database.calcular_kpis_tablero (sin
#     filtro de mes -- es una foto de "ahora mismo": cuántos tickets entraron
#     este mes calendario y cuánto llevan ahora mismo en cada columna del
#     tablero), para que el reporte cubra TODOS los KPIs del sistema y no
#     solo los del Dashboard.
# ---------------------------------------------------------------------------

def informe_kpis_excel_bytes(periodo_texto: str, filtros_texto: str, kpis: dict, kpis_tablero: dict) -> bytes:
    """Genera el reporte de KPIs en Excel (.xlsx), con formato claro para
    revisar en una hoja de cálculo: una tabla por sección (resumen general,
    por rubro con su tiempo promedio, por empresa, y el resumen en vivo del
    Tablero). Requiere 'openpyxl' (ver requirements.txt)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "KPIs"

    AZUL_OSCURO = "14243C"
    GRIS_CLARO = "F2F2F2"
    BLANCO = "FFFFFF"
    BORDE = Border(*(Side(style="thin", color="D0D0D0"),) * 4)

    fila = 1

    def titulo(texto, tam=14, negro_sobre_azul=True):
        nonlocal fila
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=4)
        celda = ws.cell(row=fila, column=1, value=texto)
        celda.font = Font(bold=True, size=tam, color=BLANCO if negro_sobre_azul else "000000")
        if negro_sobre_azul:
            for c in range(1, 5):
                ws.cell(row=fila, column=c).fill = PatternFill("solid", fgColor=AZUL_OSCURO)
        celda.alignment = Alignment(vertical="center")
        ws.row_dimensions[fila].height = 22 if tam >= 14 else 18
        fila += 1

    def subtitulo(texto):
        nonlocal fila
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=4)
        celda = ws.cell(row=fila, column=1, value=texto)
        celda.font = Font(bold=True, size=11, color="FFFFFF")
        for c in range(1, 5):
            ws.cell(row=fila, column=c).fill = PatternFill("solid", fgColor="2E4053")
        fila += 1

    def encabezados(*textos):
        nonlocal fila
        for i, texto in enumerate(textos, start=1):
            celda = ws.cell(row=fila, column=i, value=texto)
            celda.font = Font(bold=True)
            celda.fill = PatternFill("solid", fgColor=GRIS_CLARO)
            celda.border = BORDE
            celda.alignment = Alignment(horizontal="left" if i == 1 else "center")
        fila += 1

    def renglon(*valores):
        nonlocal fila
        for i, valor in enumerate(valores, start=1):
            celda = ws.cell(row=fila, column=i, value=valor)
            celda.border = BORDE
            celda.alignment = Alignment(horizontal="left" if i == 1 else "center")
        fila += 1

    def espacio():
        nonlocal fila
        fila += 1

    titulo(f"Reporte de KPIs — Sistema de Soporte TI — {EMPRESA_NOMBRE}")
    ws.cell(row=fila, column=1, value=f"Periodo: {periodo_texto}").font = Font(italic=True)
    fila += 1
    ws.cell(row=fila, column=1, value=f"Filtros aplicados: {filtros_texto}").font = Font(italic=True)
    fila += 1
    from datetime import datetime as _dt
    ws.cell(row=fila, column=1, value=f"Generado: {_dt.now().strftime('%d/%m/%Y %H:%M')}").font = Font(italic=True, size=9, color="808080")
    espacio()

    subtitulo("Resumen general del periodo")
    encabezados("Indicador", "Valor")
    renglon("Tickets creados", kpis["creados"])
    renglon("Tickets cerrados", kpis["cerrados"])
    renglon("Tiempo promedio de resolución", formatear_horas(kpis["horas_promedio_resolucion"]))
    renglon("Resolución más rápida", formatear_horas(kpis["horas_resolucion_minima"]))
    renglon("Resolución más lenta", formatear_horas(kpis["horas_resolucion_maxima"]))
    espacio()

    subtitulo("Por tipo de solicitud (rubro)")
    encabezados("Rubro", "Creados", "Cerrados", "Tiempo promedio")
    for cat in CATEGORIAS_TICKET:
        renglon(
            cat,
            kpis["por_categoria_creados"].get(cat, 0),
            kpis["por_categoria_cerrados"].get(cat, 0),
            formatear_horas(kpis["horas_promedio_por_categoria"].get(cat)),
        )
    espacio()

    subtitulo("Por empresa")
    encabezados("Empresa", "Creados", "Cerrados")
    for emp in EMPRESAS_TICKET:
        renglon(emp, kpis["por_empresa_creados"].get(emp, 0), kpis["por_empresa_cerrados"].get(emp, 0))
    espacio()

    subtitulo("Resumen en vivo del Tablero (a la fecha de generación)")
    encabezados("Indicador", "Valor")
    renglon("Tickets creados este mes calendario", kpis_tablero["tickets_mes"])
    for cat in CATEGORIAS_TICKET:
        renglon(f"  {cat} — este mes", kpis_tablero["por_categoria_mes"].get(cat, 0))
    espacio()
    encabezados("Estado del tablero", "Tiempo promedio actual")
    for estado in ESTADOS_TICKET:
        renglon(estado, formatear_horas(kpis_tablero["horas_promedio_por_estado"].get(estado)))

    anchos = [42, 24, 16, 24]
    for i, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    # Que al imprimir (o exportar a PDF desde Excel) quepan las 4 columnas
    # en el ancho de una sola hoja, en vez de partirse en varias páginas.
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    import io
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def informe_kpis_pdf_bytes(periodo_texto: str, filtros_texto: str, kpis: dict, kpis_tablero: dict) -> bytes:
    """Genera el reporte de KPIs como PDF con estilo de informe ejecutivo
    gerencial (título, franjas de color por sección, tablas) — listo para
    imprimir o adjuntar en un correo a Junta Directiva. Sin logo (a pedido
    de Steven)."""
    from datetime import datetime as _dt

    AZUL_OSCURO = (20, 36, 60)
    GRIS_CLARO = (242, 242, 242)
    GRIS_TEXTO = (90, 90, 90)

    pdf = FPDF(format="Letter")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # -- Encabezado -- (sin logo, a pedido de Steven -- el título arranca
    # directo en el margen izquierdo).
    TEXTO_X = 10
    pdf.set_xy(TEXTO_X, 10)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*AZUL_OSCURO)
    pdf.cell(0, 7, _pdf_safe("Informe Ejecutivo de KPIs — Sistema de Soporte TI"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(TEXTO_X)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GRIS_TEXTO)
    pdf.cell(0, 6, _pdf_safe(f"{EMPRESA_NOMBRE} · Periodo: {periodo_texto}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(TEXTO_X)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, _pdf_safe(f"Filtros aplicados: {filtros_texto}"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(32)
    pdf.set_draw_color(*AZUL_OSCURO)
    pdf.set_line_width(0.6)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    def franja_titulo(texto):
        pdf.set_fill_color(*AZUL_OSCURO)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, _pdf_safe(f"  {texto}"), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    def tabla(encabezados, filas, anchos):
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_fill_color(*GRIS_CLARO)
        for texto, ancho in zip(encabezados, anchos):
            pdf.cell(ancho, 7, _pdf_safe(texto), border=1, align="C", fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 9.5)
        for fila_datos in filas:
            for valor, ancho in zip(fila_datos, anchos):
                pdf.cell(ancho, 7, _pdf_safe(valor), border=1, align="C")
            pdf.ln()
        pdf.ln(4)

    franja_titulo("Resumen general del periodo")
    tabla(
        ["Tickets creados", "Tickets cerrados", "Tiempo promedio de resolución"],
        [[kpis["creados"], kpis["cerrados"], formatear_horas(kpis["horas_promedio_resolucion"])]],
        [63, 63, 64],
    )
    tabla(
        ["Resolución más rápida", "Resolución más lenta"],
        [[formatear_horas(kpis["horas_resolucion_minima"]), formatear_horas(kpis["horas_resolucion_maxima"])]],
        [95, 95],
    )

    franja_titulo("Por tipo de solicitud (rubro)")
    tabla(
        ["Rubro", "Creados", "Cerrados", "Tiempo promedio"],
        [
            [
                cat,
                kpis["por_categoria_creados"].get(cat, 0),
                kpis["por_categoria_cerrados"].get(cat, 0),
                formatear_horas(kpis["horas_promedio_por_categoria"].get(cat)),
            ]
            for cat in CATEGORIAS_TICKET
        ],
        [70, 40, 40, 40],
    )

    franja_titulo("Por empresa")
    tabla(
        ["Empresa", "Creados", "Cerrados"],
        [
            [emp, kpis["por_empresa_creados"].get(emp, 0), kpis["por_empresa_cerrados"].get(emp, 0)]
            for emp in EMPRESAS_TICKET
        ],
        [90, 50, 50],
    )

    if pdf.get_y() > 220:
        pdf.add_page()

    franja_titulo("Resumen en vivo del Tablero (a la fecha de generación)")
    filas_tablero = [["Tickets creados este mes calendario", kpis_tablero["tickets_mes"]]]
    filas_tablero += [
        [f"  {cat} — este mes", kpis_tablero["por_categoria_mes"].get(cat, 0)] for cat in CATEGORIAS_TICKET
    ]
    tabla(["Indicador", "Valor"], filas_tablero, [140, 50])
    tabla(
        ["Estado del tablero", "Tiempo promedio que llevan ahí ahora"],
        [[estado, formatear_horas(kpis_tablero["horas_promedio_por_estado"].get(estado))] for estado in ESTADOS_TICKET],
        [95, 95],
    )

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(140, 140, 140)
    pdf.multi_cell(
        0, 5,
        _pdf_safe(
            f"Informe generado automáticamente por Sistema IT — {EMPRESA_NOMBRE} — "
            f"{_dt.now().strftime('%d/%m/%Y %H:%M')}."
        ),
    )

    return bytes(pdf.output())


# ---------------------------------------------------------------------------
# Descargar los datos del Tablero (Excel y Word) — ver
# pages/1_Sistema_IT.py, botones "📊 Descargar Excel" / "📝 Descargar Word"
# debajo del filtro "Filtrar por tipo". Ambas funciones reciben:
#   - filas: una lista de dicts YA ARMADA por la página (ver
#     pages/1_Sistema_IT.py:_filas_exportables_tablero), uno por ticket
#     actualmente en el tablero (con el filtro de tipo que tenga puesto),
#     con las llaves: numero, categoria, urgencia, estado, tiempo_en_estado
#     (ya formateado, ej. "3 h"), empresa, area, asignado_a, solicitante,
#     correo, telefono, descripcion, creado_en (ya formateada, dd/mm/aaaa).
#     Este archivo (utils.py) no importa database.py a propósito (sería un
#     import circular -- database.py ya importa de aquí), así que el
#     cálculo de "cuánto lleva en su estado" y el resto de campos se hacen
#     en la página, no aquí.
#   - filtro_texto: p.ej. "Tipo: Soporte Técnico" o "Todos los tipos".
# ---------------------------------------------------------------------------

_COLUMNAS_TABLERO = [
    ("numero", "Ticket"),
    ("categoria", "Categoría"),
    ("urgencia", "Urgencia"),
    ("estado", "Estado"),
    ("tiempo_en_estado", "Tiempo en estado"),
    ("empresa", "Empresa"),
    ("area", "Área"),
    ("asignado_a", "Asignado a"),
    ("solicitante", "Solicitante"),
    ("correo", "Correo"),
    ("telefono", "Teléfono"),
    ("descripcion", "Descripción"),
    ("creado_en", "Creado"),
]


def tablero_excel_bytes(filas: list, filtro_texto: str) -> bytes:
    """Genera el Excel (.xlsx) con los tickets que están AHORA MISMO en el
    tablero (Nuevo/Asignado/En proceso/Resuelto — los que todavía no pasan a
    Historial), uno por fila, con el mismo filtro de tipo que tengas puesto
    en pantalla. Requiere 'openpyxl'."""
    from datetime import datetime as _dt
    import io

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Tablero"

    AZUL_OSCURO = "14243C"
    GRIS_CLARO = "F2F2F2"
    n_cols = len(_COLUMNAS_TABLERO)
    BORDE = Border(*(Side(style="thin", color="D0D0D0"),) * 4)

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    celda = ws.cell(row=1, column=1, value=f"Tablero de tickets — Sistema de Soporte TI — {EMPRESA_NOMBRE}")
    celda.font = Font(bold=True, size=14, color="FFFFFF")
    for c in range(1, n_cols + 1):
        ws.cell(row=1, column=c).fill = PatternFill("solid", fgColor=AZUL_OSCURO)
    ws.row_dimensions[1].height = 22

    ws.cell(row=2, column=1, value=f"Filtro: {filtro_texto}").font = Font(italic=True)
    ws.cell(row=3, column=1, value=f"Generado: {_dt.now().strftime('%d/%m/%Y %H:%M')}").font = Font(
        italic=True, size=9, color="808080"
    )

    fila_encabezado = 5
    for i, (_clave, titulo) in enumerate(_COLUMNAS_TABLERO, start=1):
        celda = ws.cell(row=fila_encabezado, column=i, value=titulo)
        celda.font = Font(bold=True)
        celda.fill = PatternFill("solid", fgColor=GRIS_CLARO)
        celda.border = BORDE
        celda.alignment = Alignment(horizontal="center")

    for f, datos in enumerate(filas, start=fila_encabezado + 1):
        for i, (clave, _titulo) in enumerate(_COLUMNAS_TABLERO, start=1):
            celda = ws.cell(row=f, column=i, value=datos.get(clave, "—"))
            celda.border = BORDE
            celda.alignment = Alignment(horizontal="left" if i in (1, 12) else "center", wrap_text=(i == 12))

    anchos = [10, 16, 12, 12, 16, 16, 16, 18, 20, 26, 14, 44, 12]
    for i, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho

    ws.freeze_panes = f"A{fila_encabezado + 1}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def tablero_word_bytes(filas: list, filtro_texto: str) -> bytes:
    """Genera el Word (.docx) con los mismos tickets que tablero_excel_bytes
    (ver arriba), en una tabla apaisada -- para compartir o imprimir el
    estado del flujo de trabajo. Requiere 'python-docx'."""
    from datetime import datetime as _dt
    import io

    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    def _fondo_celda(celda, color_hex):
        """Rellena el fondo de una celda de tabla — python-docx no trae un
        atajo para esto, hay que armar el elemento XML 'w:shd' a mano."""
        sombreado = OxmlElement("w:shd")
        sombreado.set(qn("w:val"), "clear")
        sombreado.set(qn("w:color"), "auto")
        sombreado.set(qn("w:fill"), color_hex)
        celda._tc.get_or_add_tcPr().append(sombreado)

    doc = Document()

    # Orientación horizontal -- si no, una tabla de 13 columnas no cabe.
    seccion = doc.sections[0]
    seccion.orientation = WD_ORIENT.LANDSCAPE
    seccion.page_width, seccion.page_height = seccion.page_height, seccion.page_width
    seccion.left_margin = seccion.right_margin = Inches(0.4)
    seccion.top_margin = seccion.bottom_margin = Inches(0.5)

    titulo = doc.add_heading(f"Tablero de tickets — Sistema de Soporte TI — {EMPRESA_NOMBRE}", level=1)
    for run in titulo.runs:
        run.font.color.rgb = RGBColor(0x14, 0x24, 0x3C)

    p_filtro = doc.add_paragraph()
    p_filtro.add_run(f"Filtro: {filtro_texto}").italic = True
    p_generado = doc.add_paragraph()
    run_generado = p_generado.add_run(f"Generado: {_dt.now().strftime('%d/%m/%Y %H:%M')}")
    run_generado.italic = True
    run_generado.font.size = Pt(8)
    run_generado.font.color.rgb = RGBColor(0x80, 0x80, 0x80)

    if not filas:
        doc.add_paragraph("No hay tickets en el tablero con ese filtro.")
    else:
        tabla = doc.add_table(rows=1, cols=len(_COLUMNAS_TABLERO))
        tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
        tabla.style = "Table Grid"

        celdas_encabezado = tabla.rows[0].cells
        for i, (_clave, titulo_col) in enumerate(_COLUMNAS_TABLERO):
            celdas_encabezado[i].text = titulo_col
            for p in celdas_encabezado[i].paragraphs:
                for run in p.runs:
                    run.bold = True
                    run.font.size = Pt(8)
            _fondo_celda(celdas_encabezado[i], "D9D9D9")

        for datos in filas:
            celdas = tabla.add_row().cells
            for i, (clave, _titulo_col) in enumerate(_COLUMNAS_TABLERO):
                celdas[i].text = str(datos.get(clave, "—"))
                for p in celdas[i].paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(8)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
