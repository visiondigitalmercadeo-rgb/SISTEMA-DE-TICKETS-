import streamlit as st

import auth
import database as db
from config import (
    CATEGORIAS_TICKET, EMPRESA_NOMBRE, ESTADO_EMOJI, ESTADOS_TICKET, FAVICON_PATH, LOGO_SOPORTE_PATH,
    TICKET_SIGUIENTE_ESTADO,
)

st.set_page_config(page_title=f"Sistema IT — {EMPRESA_NOMBRE}", page_icon=FAVICON_PATH, layout="wide")
st.logo(LOGO_SOPORTE_PATH, size="large")

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


def _categorias_validas(tecnico):
    """Las 'categorías que atiende' guardadas del técnico, descartando
    cualquiera que ya no exista en config.CATEGORIAS_TICKET (por ejemplo si
    se renombró o se quitó una categoría después de asignársela a alguien).
    Lista vacía = puede atender todas las categorías actuales."""
    accesos = tecnico.get("categorias_acceso") or []
    return [a for a in accesos if a in CATEGORIAS_TICKET]


def _puede_atender(tecnico, categoria):
    """True si el técnico puede atender esa categoría de ticket — según sus
    'categorías que atiende'; una lista vacía significa 'todas'."""
    accesos = _categorias_validas(tecnico)
    return not accesos or categoria in accesos


def _formatear_horas(horas):
    if horas is None:
        return "—"
    if horas < 48:
        return f"{horas:.0f} h"
    return f"{horas / 24:.1f} d"


def _dibujar_kpis():
    kpis = db.calcular_kpis_tablero(db.list_tickets())

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
            _formatear_horas(kpis["horas_promedio_por_estado"].get(estado)),
        )

    st.divider()


def _dibujar_tablero():
    st.caption("Tablero de tickets — arrástralos mentalmente de izquierda a derecha conforme avanzan.")

    _dibujar_kpis()

    filtro_categoria = st.selectbox("Filtrar por tipo", ["Todos"] + CATEGORIAS_TICKET, key="panel_filtro_categoria")
    tickets = db.list_tickets(categoria=None if filtro_categoria == "Todos" else filtro_categoria)
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
                    st.markdown(f"👤 {t['nombre_solicitante']}" + (f" · {t['contacto']}" if t.get("contacto") else ""))
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


def _fila_usuario(t, es_yo):
    tid = t["id"]
    accesos = _categorias_validas(t)
    with st.container(border=True):
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(f"**{t['nombre']}** ({t['username']})" + (" 👑 admin" if t.get("es_admin") else ""))
            st.caption(
                f"Correo: {t.get('correo') or '—'} · "
                f"Atiende: " + (", ".join(accesos) if accesos else "todas las categorías")
            )
        with c2:
            st.caption("🟢 Activo" if t.get("activo", True) else "🔴 Desactivado")
            if es_yo:
                st.caption("— tu propia cuenta —")

        tab_editar, tab_clave, tab_permisos = st.tabs(["✏️ Editar", "🔑 Contraseña", "⚙️ Permisos"])

        with tab_editar:
            with st.form(f"form_editar_{tid}"):
                nombre_ed = st.text_input("Nombre completo", value=t["nombre"], key=f"ed_nombre_{tid}")
                username_ed = st.text_input("Usuario", value=t["username"], key=f"ed_user_{tid}")
                correo_ed = st.text_input(
                    "Correo (para mandarle la Orden de Solicitud cuando le asignan un ticket)",
                    value=t.get("correo") or "", key=f"ed_correo_{tid}",
                )
                accesos_ed = st.multiselect(
                    "Categorías que atiende (vacío = todas)", CATEGORIAS_TICKET, default=accesos,
                    key=f"ed_accesos_{tid}",
                )
                if st.form_submit_button("Guardar cambios", use_container_width=True, key=f"guardar_perfil_{tid}"):
                    try:
                        db.update_it_usuario_perfil(
                            tid, nombre_ed, username_ed, categorias_acceso=accesos_ed, correo=correo_ed,
                        )
                        st.success("Datos actualizados.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

        with tab_clave:
            with st.form(f"form_clave_{tid}"):
                clave_nueva = st.text_input("Nueva contraseña", type="password", key=f"clave_{tid}")
                if st.form_submit_button("Restablecer contraseña", use_container_width=True, key=f"resetear_clave_{tid}"):
                    if not clave_nueva:
                        st.error("Escribe la nueva contraseña.")
                    else:
                        db.update_it_usuario_password(tid, clave_nueva)
                        st.success(f"Contraseña de '{t['nombre']}' actualizada. Avísale la nueva clave.")

        with tab_permisos:
            if es_yo:
                st.caption("No puedes cambiar tu propio rol, desactivarte ni eliminarte — pide a otro administrador que lo haga.")
            else:
                colp1, colp2 = st.columns(2)
                with colp1:
                    etiqueta_admin = "⬇️ Quitar administrador" if t.get("es_admin") else "⬆️ Hacer administrador"
                    if st.button(etiqueta_admin, key=f"admin_{tid}", use_container_width=True):
                        try:
                            db.set_it_usuario_admin(tid, not t.get("es_admin"))
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

                    etiqueta_activo = "Desactivar" if t.get("activo", True) else "Reactivar"
                    if st.button(etiqueta_activo, key=f"toggle_tec_{tid}", use_container_width=True):
                        try:
                            db.set_it_usuario_activo(tid, not t.get("activo", True))
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

                with colp2:
                    confirmar = st.checkbox("Confirmo que quiero eliminarlo permanentemente", key=f"confirmar_del_{tid}")
                    if st.button("🗑️ Eliminar permanentemente", key=f"del_{tid}", use_container_width=True, disabled=not confirmar):
                        try:
                            db.delete_it_usuario(tid)
                            st.success(f"'{t['nombre']}' fue eliminado.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))


def _dibujar_admin():
    st.caption("Administra las cuentas del equipo de TI: quién entra, qué rol tiene y qué categorías atiende.")

    usuarios = db.list_it_usuarios()
    for t in usuarios:
        _fila_usuario(t, es_yo=(t["id"] == user["id"]))

    st.divider()
    st.markdown("**➕ Agregar técnico**")
    with st.form("form_nuevo_tecnico", clear_on_submit=True):
        nombre_nuevo = st.text_input("Nombre completo")
        username_nuevo = st.text_input("Usuario")
        password_nuevo = st.text_input("Contraseña inicial", type="password")
        correo_nuevo = st.text_input("Correo (opcional, para mandarle la Orden de Solicitud al asignarle un ticket)")
        accesos_nuevo = st.multiselect("Categorías que atiende (vacío = todas)", CATEGORIAS_TICKET)
        es_admin_nuevo = st.checkbox("También administrador del panel (puede administrar usuarios)")
        if st.form_submit_button("Crear técnico", use_container_width=True):
            if not nombre_nuevo.strip() or not username_nuevo.strip() or not password_nuevo:
                st.error("Completa nombre, usuario y contraseña.")
            else:
                try:
                    db.create_it_usuario(
                        nombre_nuevo, username_nuevo, password_nuevo,
                        es_admin=es_admin_nuevo, categorias_acceso=accesos_nuevo, correo=correo_nuevo,
                    )
                    st.success(f"'{nombre_nuevo}' agregado al equipo de TI.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.divider()
    st.markdown("**✉️ Correos de aviso por categoría**")
    st.caption(
        "Cada vez que un solicitante reporta un problema, se manda automáticamente un correo (con la "
        "Orden de Solicitud en PDF adjunta) a la lista de abajo (según la categoría del ticket) y, si el "
        "solicitante dejó un correo válido, también se le confirma a él que su ticket quedó registrado. "
        "Cuando después alguien del equipo toma el ticket, se le vuelve a mandar la orden directo a su "
        "correo (el que le pongas en 'Editar' de cada técnico, más abajo)."
    )
    if not db.correo_disponible():
        st.info(
            "Todavía no está configurado el correo que manda los avisos (falta conectar una cuenta de "
            "Gmail en los secretos de Streamlit Cloud — la misma que ya usa la plataforma comercial para "
            "las Minutas de Tienda; solo hay que copiar el mismo bloque `[gmail_notificaciones]`). "
            "Mientras tanto no se manda nada, pero puedes ir guardando los correos de una vez."
        )
    for categoria in CATEGORIAS_TICKET:
        correos_actuales = db.get_it_correos_aviso(categoria)
        with st.form(f"form_correos_aviso_{categoria}"):
            correos_texto = st.text_area(
                f"Correos que reciben aviso de tickets de '{categoria}'",
                value="\n".join(correos_actuales),
                placeholder="uno por línea, o separados por coma",
                key=f"correos_aviso_texto_{categoria}", height=80,
            )
            if st.form_submit_button(f"💾 Guardar correos de {categoria}", use_container_width=True):
                nuevos_correos = [c.strip() for c in correos_texto.replace(",", "\n").split("\n") if c.strip()]
                db.set_it_correos_aviso(categoria, nuevos_correos)
                st.success("Correos actualizados.")
                st.rerun()


if user["es_admin"]:
    tab_tablero, tab_admin = st.tabs(["📋 Tablero", "🔐 Administrador"])
    with tab_tablero:
        _dibujar_tablero()
    with tab_admin:
        _dibujar_admin()
else:
    _dibujar_tablero()
