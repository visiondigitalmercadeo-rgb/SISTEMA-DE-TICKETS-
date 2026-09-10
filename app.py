import streamlit as st

import auth
import database as db
from config import (
    AREAS_POR_EMPRESA, CATEGORIA_DESCRIPCION, CATEGORIAS_TICKET, EMPRESA_NOMBRE, EMPRESAS_TICKET,
    ESCRIBIR_AREA_NUEVA, ESTADO_EMOJI, FAVICON_PATH, LOGO_SOPORTE_PATH, TICKET_FOTO_MAX_BYTES,
    URGENCIA_DEFECTO, URGENCIA_DESCRIPCION, URGENCIAS_TICKET,
)
from utils import archivo_a_b64, orden_trabajo_pdf_bytes, urgencia_badge_html

st.set_page_config(page_title=f"Soporte TI — {EMPRESA_NOMBRE}", page_icon=FAVICON_PATH, layout="centered")
auth.mostrar_logo_sidebar()

if not db.firebase_conectado():
    st.warning(
        "⚠️ **Firebase todavía no está conectado.** Estás viendo esta app en **modo de práctica**: "
        "los tickets son temporales y se pierden al cerrar el servidor. Agrega las credenciales de "
        "Firebase en los secretos de Streamlit Cloud (las mismas que usa la plataforma comercial) "
        "para guardar tickets de verdad.",
        icon="⚠️",
    )

_, col_logo, _ = st.columns([1, 1.2, 1])
with col_logo:
    try:
        st.image(LOGO_SOPORTE_PATH, use_container_width=True)
    except Exception:
        pass
st.title("🛠️ Soporte Técnico y de Sistemas")

st.divider()

tab_nuevo, tab_consultar = st.tabs(["📝 Reportar un problema", "🔍 Consultar un ticket"])

# ---------------------------------------------------------------------------
# Reportar un problema — widgets sueltos (NO st.form): el selector de área
# necesita revelar un campo de texto en cuanto se elige "Otra (escribir)", y
# eso solo pasa con un rerun inmediato, cosa que un st.form no hace hasta que
# se presiona el botón de enviar (mismo motivo por el que Minutas de Tienda,
# en la plataforma comercial, tampoco usa st.form para su formulario).
# ---------------------------------------------------------------------------
with tab_nuevo:
    st.session_state.setdefault("ticket_form_key", 0)
    sufijo = st.session_state["ticket_form_key"]

    nombre = st.text_input("Nombre completo *", key=f"ti_nombre_{sufijo}")
    correo = st.text_input("Correo electrónico *", key=f"ti_correo_{sufijo}")
    telefono = st.text_input("Teléfono *", key=f"ti_telefono_{sufijo}")

    # Si llegaron aquí escaneando el código QR de una empresa (ver
    # Administrador → 📱 Código QR de acceso), el link trae "?empresa=..." y
    # se preselecciona esa empresa en vez de la primera de la lista.
    _empresa_qp = st.query_params.get("empresa")
    _empresa_index = EMPRESAS_TICKET.index(_empresa_qp) if _empresa_qp in EMPRESAS_TICKET else 0
    empresa = st.selectbox("Empresa", EMPRESAS_TICKET, index=_empresa_index, key=f"ti_empresa_{sufijo}")
    areas_disponibles = AREAS_POR_EMPRESA.get(empresa, [])
    area_sel = st.selectbox("Tienda / área", areas_disponibles + [ESCRIBIR_AREA_NUEVA], key=f"ti_area_sel_{sufijo}")
    if area_sel == ESCRIBIR_AREA_NUEVA:
        area_final = st.text_input("¿Cuál área?", key=f"ti_area_otra_{sufijo}")
    else:
        area_final = area_sel

    categoria = st.radio(
        "Tipo de solicitud *", CATEGORIAS_TICKET,
        captions=[CATEGORIA_DESCRIPCION[c] for c in CATEGORIAS_TICKET], key=f"ti_categoria_{sufijo}",
    )
    urgencia = st.radio(
        "Urgencia *", URGENCIAS_TICKET,
        captions=[URGENCIA_DESCRIPCION[u] for u in URGENCIAS_TICKET],
        index=URGENCIAS_TICKET.index(URGENCIA_DEFECTO), horizontal=True, key=f"ti_urgencia_{sufijo}",
    )
    descripcion = st.text_area("Describe tu problema *", key=f"ti_descripcion_{sufijo}", height=120)
    foto = st.file_uploader(
        "Adjuntar una foto o captura de pantalla (opcional)", type=["png", "jpg", "jpeg", "pdf"],
        help=f"Tamaño máximo: ~{TICKET_FOTO_MAX_BYTES // 1000} KB.", key=f"ti_foto_{sufijo}",
    )

    if st.button("📨 Enviar solicitud", key=f"ti_enviar_{sufijo}", use_container_width=True):
        if not nombre.strip() or not correo.strip() or not telefono.strip() or not descripcion.strip():
            st.error("Completa tu nombre, correo, teléfono y la descripción del problema.")
        elif not db.correo_es_valido(correo):
            st.error("Escribe un correo electrónico válido (ej. nombre@dominio.com).")
        else:
            foto_b64 = foto_nombre = foto_tipo = None
            error_foto = None
            if foto is not None:
                try:
                    foto_b64, foto_nombre, foto_tipo = archivo_a_b64(foto, TICKET_FOTO_MAX_BYTES)
                except ValueError as e:
                    error_foto = str(e)

            if error_foto:
                st.error(error_foto)
            else:
                numero = db.create_ticket(
                    nombre, correo, telefono, area_final, categoria, descripcion,
                    empresa=empresa, urgencia=urgencia, foto_b64=foto_b64, foto_nombre=foto_nombre,
                    foto_tipo=foto_tipo,
                )
                st.session_state["ticket_form_key"] += 1  # limpia el formulario (nuevos keys = nuevos widgets)
                st.success(
                    f"✅ ¡Listo! Tu ticket es **#TI-{numero:04d}**. Guárdalo para consultar el estado en "
                    "la pestaña 'Consultar un ticket'. El equipo de TI le dará seguimiento pronto."
                )

# ---------------------------------------------------------------------------
# Consultar un ticket — cualquiera con el número puede ver su estado y el
# historial de seguimiento, sin necesitar cuenta ni contraseña.
# ---------------------------------------------------------------------------
with tab_consultar:
    numero_txt = st.text_input("Número de ticket (ej. TI-0004 o solo 4)", key="ti_consulta_numero")
    if st.button("Buscar", key="ti_consulta_buscar"):
        digitos = "".join(c for c in numero_txt if c.isdigit())
        ticket = db.get_ticket_por_numero(int(digitos)) if digitos else None
        if not ticket:
            st.warning("No se encontró ningún ticket con ese número.")
        else:
            st.markdown(f"### {ESTADO_EMOJI.get(ticket['estado'], '•')} Ticket #TI-{ticket['numero']:04d} — {ticket['estado']}")
            st.markdown(urgencia_badge_html(ticket.get("urgencia")), unsafe_allow_html=True)
            st.caption(
                f"{ticket['categoria']} · {ticket.get('empresa') or '—'} · {ticket.get('area') or '—'} · "
                f"reportado por {ticket['nombre_solicitante']}"
            )
            st.write(ticket["descripcion"])
            if ticket.get("asignado_a_nombre"):
                st.caption(f"👤 Asignado a: {ticket['asignado_a_nombre']}")
            historial = ticket.get("historial") or []
            if historial:
                with st.expander(f"📜 Historial ({len(historial)})"):
                    for h in historial:
                        st.caption(f"🕒 {(h.get('fecha') or '')[:16].replace('T', ' ')} — {h.get('detalle')}")

            try:
                st.download_button(
                    "📄 Descargar Orden de Trabajo (PDF)",
                    data=orden_trabajo_pdf_bytes(ticket),
                    file_name=f"TI-{ticket['numero']:04d}.pdf", mime="application/pdf",
                    use_container_width=True, key="ti_consulta_descargar_pdf",
                )
            except Exception:
                pass
