from datetime import datetime

import streamlit as st

import auth
import database as db
from config import (
    CATEGORIAS_TICKET, EMPRESA_NOMBRE, ESTADO_EMOJI, ESTADOS_TICKET, FAVICON_PATH, MESES_ES,
    TICKET_SIGUIENTE_ESTADO,
)
from utils import formatear_horas, orden_solicitud_pdf_bytes

st.set_page_config(page_title=f"Sistema IT — {EMPRESA_NOMBRE}", page_icon=FAVICON_PATH, layout="wide")
auth.mostrar_logo_sidebar()

if not auth.require_login():
    st.stop()

user = auth.current_user()

with st.sidebar:
    st.markdown(f"**{user['nombre']}**")
    st.caption("Administrador" if user["es_admin"] else "Técnico")
    if st.button("🔄 Actualizar", use_container_width=True):
        st.rerun()
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        auth.do_logout()
        st.rerun()

st.title("🛠️ Sistema IT")


def _puede_atender(tecnico, categoria):
    """True si el técnico puede atender esa categoría de ticket — según sus
    'categorías que atiende'; una lista vacía significa 'todas'."""
    accesos = db.categorias_validas_tecnico(tecnico)
    return not accesos or categoria in accesos


def _dibujar_kpis():
    todos = db.list_tickets()
    # Los que ya se archivaron a Historial no deben contar en "tiempo que
    # llevan ahora mismo en cada columna" — si no, un ticket resuelto hace
    # meses inflaría para siempre el promedio de la columna "Resuelto".
    activos = [t for t in todos if not db.ticket_es_historico(t)]
    kpis = db.calcular_kpis_tablero(todos, activos)

    st.markdown("##### 📊 Tickets de este mes")
    cols_mes = st.columns(1 + len(CATEGORIAS_TICKET))
    cols_mes[0].metric("Total", kpis["tickets_mes"])
    for i, categoria in enumerate(CATEGORIAS_TICKET):
        cols_mes[i + 1].metric(categoria, kpis["por_categoria_mes"].get(categoria, 0))

    st.caption("⏱️ Tiempo que llevan ahora mismo los tickets en cada columna (promedio)")
    cols_tiempo = st.columns(len(ESTADOS_TICKET))
    for col, estado in zip(cols_tiempo, ESTADOS_TICKET):
        col.metric(
            f"{ESTADO_EMOJI.get(estado, '')} {estado}",
            formatear_horas(kpis["horas_promedio_por_estado"].get(estado)),
        )

    st.divider()


def _dibujar_tablero():
    st.caption("Tablero de tickets — arrástralos mentalmente de izquierda a derecha conforme avanzan.")

    _dibujar_kpis()

    filtro_categoria = st.selectbox("Filtrar por tipo", ["Todos"] + CATEGORIAS_TICKET, key="panel_filtro_categoria")
    tickets = db.list_tickets(categoria=None if filtro_categoria == "Todos" else filtro_categoria)
    # Los que ya llevan un día completo como "Resuelto" (o quedaron
    # "Cerrado" del flujo viejo) ya no se muestran aquí — pasaron solo a la
    # sección "Historial", sin eliminarse.
    tickets = [t for t in tickets if not db.ticket_es_historico(t)]
    tecnicos_activos = db.list_it_usuarios(solo_activos=True)

    columnas = st.columns(len(ESTADOS_TICKET))
    for col, estado in zip(columnas, ESTADOS_TICKET):
        tickets_col = [t for t in tickets if t["estado"] == estado]
        with col:
            st.markdown(f"#### {ESTADO_EMOJI.get(estado, '')} {estado} ({len(tickets_col)})")
            for t in tickets_col:
                tid = t["id"]
                with st.container(border=True):
                    st.markdown(f"**#TI-{t['numero']:04d}**")
                    st.caption(f"{t['categoria']} · {t.get('empresa') or '—'} · {t.get('area') or '—'}")
                    # "contacto" es el campo viejo (antes de separar correo y
                    # teléfono) — se usa como respaldo solo para tickets
                    # creados antes de ese cambio.
                    datos_contacto = " · ".join(
                        filter(None, [t.get("correo") or t.get("contacto"), t.get("telefono")])
                    )
                    st.markdown(f"👤 {t['nombre_solicitante']}" + (f" · {datos_contacto}" if datos_contacto else ""))
                    st.write(t["descripcion"][:160] + ("…" if len(t["descripcion"]) > 160 else ""))

                    if t.get("asignado_a_nombre"):
                        st.caption(f"🔧 Asignado a: {t['asignado_a_nombre']}")

                    if t.get("foto_b64"):
                        import base64
                        st.download_button(
                            f"📎 {t.get('foto_nombre') or 'archivo adjunto'}",
                            data=base64.b64decode(t["foto_b64"]), file_name=t.get("foto_nombre") or "adjunto",
                            mime=t.get("foto_tipo") or "application/octet-stream",
                            use_container_width=True, key=f"panel_foto_{tid}",
                        )

                    try:
                        st.download_button(
                            "📄 Orden de Solicitud (PDF)",
                            data=orden_solicitud_pdf_bytes(t), file_name=f"TI-{t['numero']:04d}.pdf",
                            mime="application/pdf", use_container_width=True, key=f"panel_orden_pdf_{tid}",
                        )
                    except Exception:
                        pass

                    # Asignar / reasignar técnico — solo se ofrecen los que
                    # pueden atender esta categoría (según sus "categorías
                    # que atiende"; si no tiene ninguna marcada, puede con
                    # todas).
                    candidatos = [tec for tec in tecnicos_activos if _puede_atender(tec, t["categoria"])]
                    if candidatos:
                        opciones_tec = {"— Sin asignar —": None}
                        opciones_tec.update({tec["nombre"]: tec["id"] for tec in candidatos})
                        actual = t.get("asignado_a_nombre") or "— Sin asignar —"
                        elegido = st.selectbox(
                            "Asignar a", list(opciones_tec.keys()),
                            index=list(opciones_tec.keys()).index(actual) if actual in opciones_tec else 0,
                            key=f"panel_asignar_{tid}", label_visibility="collapsed",
                        )
                        if elegido != actual:
                            tec_id = opciones_tec[elegido]
                            if tec_id is None:
                                db.asignar_ticket(tid, None, None, autor_nombre=user["nombre"])
                            else:
                                db.asignar_ticket(tid, tec_id, elegido, autor_nombre=user["nombre"])
                            st.rerun()

                    siguiente = TICKET_SIGUIENTE_ESTADO.get(estado)
                    if siguiente and st.button(f"➡️ Mover a '{siguiente}'", key=f"panel_avanzar_{tid}", use_container_width=True):
                        db.avanzar_ticket(tid, siguiente, autor_nombre=user["nombre"])
                        st.rerun()

                    with st.expander("📜 Historial / comentar"):
                        for h in (t.get("historial") or []):
                            st.caption(f"🕒 {(h.get('fecha') or '')[:16].replace('T', ' ')} — {h.get('detalle')}")
                        comentario_nuevo = st.text_input("Agregar comentario", key=f"panel_comentario_{tid}")
                        if st.button("💬 Guardar comentario", key=f"panel_guardar_comentario_{tid}", use_container_width=True):
                            if comentario_nuevo.strip():
                                db.agregar_comentario_ticket(tid, user["nombre"], comentario_nuevo)
                                st.rerun()

                    # Eliminar ticket — solo lo ve/puede usarlo un administrador.
                    if user["es_admin"]:
                        with st.expander("🗑️ Eliminar ticket"):
                            st.caption("Esto borra el ticket por completo — no se puede deshacer.")
                            confirmar_borrado = st.checkbox(
                                "Confirmo que quiero eliminar este ticket permanentemente",
                                key=f"panel_confirmar_del_ticket_{tid}",
                            )
                            if st.button(
                                "🗑️ Eliminar ticket permanentemente", key=f"panel_del_ticket_{tid}",
                                use_container_width=True, disabled=not confirmar_borrado,
                            ):
                                db.delete_ticket(tid)
                                st.success(f"Ticket #TI-{t['numero']:04d} eliminado.")
                                st.rerun()


def _dibujar_historial():
    st.caption(
        "Tickets que ya salieron del tablero — se resolvieron y les pasó un día completo. No se "
        "eliminan, solo se archivan aquí."
    )

    todos = db.list_tickets()
    historicos = [t for t in todos if db.ticket_es_historico(t)]

    # --- KPI: cuántos se cerraron por empresa, en el mes/año elegido ---
    ahora = datetime.now()
    anios_disponibles = sorted(
        {ahora.year} | {
            datetime.fromisoformat(t["creado_en"]).year
            for t in todos if t.get("creado_en")
        },
        reverse=True,
    )
    col_mes, col_anio = st.columns(2)
    with col_mes:
        mes_sel = st.selectbox("Mes", MESES_ES, index=ahora.month - 1, key="hist_filtro_mes")
    with col_anio:
        anio_sel = st.selectbox(
            "Año", anios_disponibles,
            index=anios_disponibles.index(ahora.year) if ahora.year in anios_disponibles else 0,
            key="hist_filtro_anio",
        )
    mes_num = MESES_ES.index(mes_sel) + 1

    kpis_empresa = db.calcular_kpis_historial(historicos, anio_sel, mes_num)
    st.markdown(f"##### 📊 Cerrados en {mes_sel} {anio_sel}, por empresa")
    if kpis_empresa:
        cols = st.columns(len(kpis_empresa))
        for col, (empresa, cantidad) in zip(cols, kpis_empresa.items()):
            col.metric(empresa, cantidad)
    else:
        st.caption("Ningún ticket se cerró ese mes.")

    st.divider()

    # --- Lista de tickets del historial, filtrada por tipo ---
    filtro_categoria = st.selectbox(
        "Filtrar por tipo", ["Todos"] + CATEGORIAS_TICKET, key="hist_filtro_categoria",
    )
    lista = [t for t in historicos if filtro_categoria == "Todos" or t["categoria"] == filtro_categoria]
    lista.sort(key=lambda t: t.get("numero") or 0, reverse=True)

    if not lista:
        st.info("No hay tickets en el historial todavía.")

    for t in lista:
        tid = t["id"]
        with st.container(border=True):
            st.markdown(f"**#TI-{t['numero']:04d}** — {t['categoria']}")
            st.caption(f"{t.get('empresa') or '—'} · {t.get('area') or '—'}")
            st.markdown(f"👤 {t['nombre_solicitante']}")
            st.write(t["descripcion"][:200] + ("…" if len(t["descripcion"]) > 200 else ""))
            if t.get("asignado_a_nombre"):
                st.caption(f"🔧 Atendido por: {t['asignado_a_nombre']}")
            fecha_cierre = db.fecha_entro_a_estado_actual(t)
            if fecha_cierre:
                st.caption(f"🔒 Cerrado el {fecha_cierre[:10]}")

            with st.expander("📜 Historial completo"):
                for h in (t.get("historial") or []):
                    st.caption(f"🕒 {(h.get('fecha') or '')[:16].replace('T', ' ')} — {h.get('detalle')}")

            try:
                st.download_button(
                    "📄 Orden de Solicitud (PDF)",
                    data=orden_solicitud_pdf_bytes(t), file_name=f"TI-{t['numero']:04d}.pdf",
                    mime="application/pdf", use_container_width=True, key=f"hist_orden_pdf_{tid}",
                )
            except Exception:
                pass


tab_tablero, tab_historial = st.tabs(["📋 Tablero", "🗂️ Historial"])
with tab_tablero:
    _dibujar_tablero()
with tab_historial:
    _dibujar_historial()
