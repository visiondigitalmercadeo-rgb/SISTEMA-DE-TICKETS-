from datetime import datetime

import streamlit as st

import auth
import database as db
from config import (
    CATEGORIAS_TICKET, EMPRESA_NOMBRE, ESTADO_EMOJI, ESTADOS_TICKET, FAVICON_PATH, MESES_ES,
    TICKET_SIGUIENTE_ESTADO,
)
from utils import formatear_horas, orden_trabajo_pdf_bytes, urgencia_badge_html

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


def _horas_en_estado_actual(t):
    """Cuánto lleva 'ticket' en su columna ACTUAL (desde que entró a ese
    estado, no desde que se creó) — mismo cálculo que el promedio de
    'Tickets de este mes' de arriba (ver database.calcular_kpis_tablero),
    pero por ticket individual. None si no se pudo calcular."""
    entrada_estado = db.fecha_entro_a_estado_actual(t)
    if not entrada_estado:
        return None
    try:
        return max((datetime.now() - datetime.fromisoformat(entrada_estado)).total_seconds() / 3600, 0.0)
    except ValueError:
        return None


def _fecha_corta_export(iso_txt):
    if not iso_txt or len(iso_txt) < 10:
        return "—"
    return f"{iso_txt[8:10]}/{iso_txt[5:7]}/{iso_txt[0:4]}"


def _filas_exportables_tablero(tickets):
    """Arma la lista de filas (una por ticket) para los botones 'Descargar
    Excel'/'Descargar Word' del tablero (ver utils.tablero_excel_bytes /
    tablero_word_bytes) — con todo ya formateado a texto, listo para
    escribir directo en la hoja/tabla."""
    filas = []
    for t in tickets:
        numero = t.get("numero")
        filas.append({
            "numero": f"TI-{numero:04d}" if isinstance(numero, int) else "TI-____",
            "categoria": t.get("categoria") or "—",
            "urgencia": t.get("urgencia") or "Normal",
            "estado": t.get("estado") or "—",
            "tiempo_en_estado": formatear_horas(_horas_en_estado_actual(t)),
            "empresa": t.get("empresa") or "—",
            "area": t.get("area") or "—",
            "asignado_a": t.get("asignado_a_nombre") or "Sin asignar",
            "solicitante": t.get("nombre_solicitante") or "—",
            # "contacto" es el campo viejo (antes de separar correo y
            # teléfono) — se usa como respaldo solo para tickets creados
            # antes de ese cambio.
            "correo": t.get("correo") or t.get("contacto") or "—",
            "telefono": t.get("telefono") or "—",
            "descripcion": t.get("descripcion") or "—",
            "creado_en": _fecha_corta_export(t.get("creado_en")),
        })
    return filas


def _filas_exportables_historial(tickets):
    """Arma la lista de filas (una por ticket) para el botón 'Descargar
    Excel (cerrados)' del Historial (ver utils.historial_excel_bytes) — un
    ticket por fila, ya cerrado/archivado, con su fecha de cierre y el
    tiempo total que tardó en resolverse (desde que se creó hasta que
    entró a su estado actual/final)."""
    filas = []
    for t in tickets:
        numero = t.get("numero")
        fecha_cierre = db.fecha_entro_a_estado_actual(t)
        tiempo_resolucion = None
        creado_en = t.get("creado_en")
        if fecha_cierre and creado_en:
            try:
                tiempo_resolucion = max(
                    (datetime.fromisoformat(fecha_cierre) - datetime.fromisoformat(creado_en)).total_seconds() / 3600,
                    0.0,
                )
            except ValueError:
                tiempo_resolucion = None
        filas.append({
            "numero": f"TI-{numero:04d}" if isinstance(numero, int) else "TI-____",
            "categoria": t.get("categoria") or "—",
            "urgencia": t.get("urgencia") or "Normal",
            "empresa": t.get("empresa") or "—",
            "area": t.get("area") or "—",
            "solicitante": t.get("nombre_solicitante") or "—",
            "correo": t.get("correo") or t.get("contacto") or "—",
            "telefono": t.get("telefono") or "—",
            "asignado_a": t.get("asignado_a_nombre") or "Sin asignar",
            "creado_en": _fecha_corta_export(creado_en),
            "cerrado_en": _fecha_corta_export(fecha_cierre),
            "tiempo_resolucion": formatear_horas(tiempo_resolucion),
            "descripcion": t.get("descripcion") or "—",
        })
    return filas


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

    st.markdown("##### 👷 Tickets asignados por técnico")
    st.caption("Cuántos tickets tiene cada técnico ahora mismo en el tablero (Asignado o En proceso — sin contar los ya Resueltos ni los del Historial).")
    tecnicos = db.list_it_usuarios(solo_activos=True)
    en_curso = [t for t in activos if t.get("estado") in ("Asignado", "En proceso")]
    conteo_por_tecnico = {}
    for t in en_curso:
        nombre = t.get("asignado_a_nombre") or "Sin asignar"
        conteo_por_tecnico[nombre] = conteo_por_tecnico.get(nombre, 0) + 1
    filas_tecnicos = [
        {"Técnico": t["nombre"], "Tickets asignados": conteo_por_tecnico.get(t["nombre"], 0)}
        for t in tecnicos
    ]
    sin_asignar = conteo_por_tecnico.get("Sin asignar", 0)
    if sin_asignar:
        filas_tecnicos.append({"Técnico": "Sin asignar", "Tickets asignados": sin_asignar})
    if filas_tecnicos:
        st.dataframe(filas_tecnicos, use_container_width=True, hide_index=True)
    else:
        st.caption("Todavía no hay técnicos registrados.")

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

    # --- Descargar los datos que están AHORA MISMO en el flujo de trabajo
    # (el tablero, con el filtro de tipo de arriba ya aplicado) en Excel o
    # en Word — un ticket por fila, con su tiempo en su columna actual.
    filtro_texto_export = f"Tipo: {filtro_categoria}" if filtro_categoria != "Todos" else "Todos los tipos"
    fecha_archivo = datetime.now().strftime("%Y%m%d")
    col_dl_excel, col_dl_word = st.columns(2)
    filas_export = _filas_exportables_tablero(tickets)
    with col_dl_excel:
        try:
            from utils import tablero_excel_bytes
            st.download_button(
                "📊 Descargar Excel (tablero)",
                data=tablero_excel_bytes(filas_export, filtro_texto_export),
                file_name=f"Tablero_{EMPRESA_NOMBRE.replace(' ', '_')}_{fecha_archivo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"No se pudo generar el Excel: {e}")
    with col_dl_word:
        try:
            from utils import tablero_word_bytes
            st.download_button(
                "📝 Descargar Word (tablero)",
                data=tablero_word_bytes(filas_export, filtro_texto_export),
                file_name=f"Tablero_{EMPRESA_NOMBRE.replace(' ', '_')}_{fecha_archivo}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"No se pudo generar el Word: {e}")

    st.divider()

    columnas = st.columns(len(ESTADOS_TICKET))
    for col, estado in zip(columnas, ESTADOS_TICKET):
        tickets_col = [t for t in tickets if t["estado"] == estado]
        with col:
            st.markdown(f"#### {ESTADO_EMOJI.get(estado, '')} {estado} ({len(tickets_col)})")
            for t in tickets_col:
                tid = t["id"]
                with st.container(border=True):
                    st.markdown(
                        f"**#TI-{t['numero']:04d}** &nbsp; {urgencia_badge_html(t.get('urgencia'))}",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"{t['categoria']} · {t.get('empresa') or '—'} · {t.get('area') or '—'}")

                    # Cuánto lleva el ticket en su columna ACTUAL (desde que
                    # entró a ese estado, no desde que se creó) — mismo
                    # cálculo que el promedio de "Tickets de este mes" de
                    # arriba (ver database.calcular_kpis_tablero), pero
                    # aquí por ticket individual, para que se vea de un
                    # vistazo cuáles llevan más tiempo esperando.
                    st.caption(f"⏱️ Lleva {formatear_horas(_horas_en_estado_actual(t))} en '{estado}'")

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

                    # Si es una imagen (png/jpg/jpeg), ya va incrustada
                    # dentro de la Orden de Trabajo (ver utils.
                    # orden_trabajo_pdf_bytes) -- el botón aparte solo
                    # sigue haciendo falta para el otro tipo permitido al
                    # reportar el problema, un PDF, que no se puede
                    # incrustar como imagen.
                    if t.get("foto_b64") and not (t.get("foto_tipo") or "").lower().startswith("image/"):
                        import base64
                        st.download_button(
                            f"📎 {t.get('foto_nombre') or 'archivo adjunto'}",
                            data=base64.b64decode(t["foto_b64"]), file_name=t.get("foto_nombre") or "adjunto",
                            mime=t.get("foto_tipo") or "application/octet-stream",
                            use_container_width=True, key=f"panel_foto_{tid}",
                        )

                    try:
                        st.download_button(
                            "📄 Orden de Trabajo (PDF)",
                            data=orden_trabajo_pdf_bytes(t), file_name=f"TI-{t['numero']:04d}.pdf",
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

    # --- Descargar TODO lo del Historial: un Excel con todos los cerrados
    # (respeta el filtro de tipo de arriba, pero NO el mes/año — son
    # "todos los cerrados", como pidió Steven) y un PDF con el resumen
    # ejecutivo del mes/año elegidos arriba (reutiliza la misma agregación
    # que ya usa el Dashboard, ver database.calcular_kpis_dashboard).
    filtro_texto_export = f"Tipo: {filtro_categoria}" if filtro_categoria != "Todos" else "Todos los tipos"
    fecha_archivo = datetime.now().strftime("%Y%m%d")
    col_dl_excel, col_dl_pdf = st.columns(2)
    with col_dl_excel:
        try:
            from utils import historial_excel_bytes
            st.download_button(
                "📊 Descargar Excel (cerrados)",
                data=historial_excel_bytes(_filas_exportables_historial(lista), filtro_texto_export),
                file_name=f"Historial_{EMPRESA_NOMBRE.replace(' ', '_')}_{fecha_archivo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"No se pudo generar el Excel: {e}")
    with col_dl_pdf:
        try:
            from utils import historial_resumen_pdf_bytes
            kpis_resumen = db.calcular_kpis_dashboard(
                todos, anio_sel, mes_num, categoria=None if filtro_categoria == "Todos" else filtro_categoria,
            )
            st.download_button(
                "📄 Descargar PDF (resumen ejecutivo)",
                data=historial_resumen_pdf_bytes(f"{mes_sel} {anio_sel}", filtro_texto_export, kpis_resumen),
                file_name=f"Resumen_Historial_{EMPRESA_NOMBRE.replace(' ', '_')}_{fecha_archivo}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")

    st.divider()

    if not lista:
        st.info("No hay tickets en el historial todavía.")

    for t in lista:
        tid = t["id"]
        with st.container(border=True):
            st.markdown(
                f"**#TI-{t['numero']:04d}** — {t['categoria']} &nbsp; {urgencia_badge_html(t.get('urgencia'))}",
                unsafe_allow_html=True,
            )
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
                    "📄 Orden de Trabajo (PDF)",
                    data=orden_trabajo_pdf_bytes(t), file_name=f"TI-{t['numero']:04d}.pdf",
                    mime="application/pdf", use_container_width=True, key=f"hist_orden_pdf_{tid}",
                )
            except Exception:
                pass


tab_tablero, tab_historial = st.tabs(["📋 Tablero", "🗂️ Historial"])
with tab_tablero:
    _dibujar_tablero()
with tab_historial:
    _dibujar_historial()
