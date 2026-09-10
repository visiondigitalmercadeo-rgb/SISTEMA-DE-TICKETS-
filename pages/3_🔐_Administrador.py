from urllib.parse import quote

import streamlit as st

import auth
import database as db
from config import CATEGORIAS_TICKET, EMPRESA_NOMBRE, EMPRESAS_TICKET, FAVICON_PATH
from utils import generar_qr_png

st.set_page_config(page_title=f"Administrador — {EMPRESA_NOMBRE}", page_icon=FAVICON_PATH, layout="wide")
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

st.title("🔐 Administrador")

if not user["es_admin"]:
    st.error("Esta sección es solo para administradores. Pide a un administrador que te dé acceso si lo necesitas.")
    st.stop()

st.caption("Administra las cuentas del equipo de TI: quién entra, qué rol tiene y qué categorías atiende.")


def _fila_usuario(t, es_yo):
    tid = t["id"]
    accesos = db.categorias_validas_tecnico(t)
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

        if st.button("← Volver a la lista", key=f"volver_lista_{tid}"):
            st.session_state["admin_editando_id"] = None
            st.rerun()

        tab_editar, tab_clave, tab_permisos = st.tabs(["✏️ Editar", "🔑 Contraseña", "⚙️ Permisos"])

        with tab_editar:
            with st.form(f"form_editar_{tid}"):
                nombre_ed = st.text_input("Nombre completo", value=t["nombre"], key=f"ed_nombre_{tid}")
                username_ed = st.text_input("Usuario", value=t["username"], key=f"ed_user_{tid}")
                correo_ed = st.text_input(
                    "Correo (para mandarle la Orden de Trabajo cuando le asignan un ticket)",
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
                            st.session_state["admin_editando_id"] = None
                            st.success(f"'{t['nombre']}' fue eliminado.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))


st.session_state.setdefault("admin_editando_id", None)

tab_usuarios, tab_qr, tab_correos = st.tabs(["👥 Usuarios", "📱 Código QR", "✉️ Correos"])

# ---------------------------------------------------------------------------
# 👥 Usuarios — ver/editar el equipo de TI ya creado, y agregar gente nueva.
# ---------------------------------------------------------------------------
with tab_usuarios:
    usuarios = db.list_it_usuarios()
    editando = next((t for t in usuarios if t["id"] == st.session_state["admin_editando_id"]), None)

    if editando:
        # Solo se muestra el detalle completo (Editar / Contraseña /
        # Permisos) de la persona seleccionada, para no tener que hacer
        # scroll entre formularios de todo el equipo para editar a una
        # sola persona.
        _fila_usuario(editando, es_yo=(editando["id"] == user["id"]))
    else:
        st.caption(f"{len(usuarios)} cuenta(s) del equipo de TI — selecciona una para editarla.")
        for t in usuarios:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"**{t['nombre']}** ({t['username']})" + (" 👑 admin" if t.get("es_admin") else ""))
                    accesos = db.categorias_validas_tecnico(t)
                    st.caption("Atiende: " + (", ".join(accesos) if accesos else "todas las categorías"))
                with c2:
                    st.caption("🟢 Activo" if t.get("activo", True) else "🔴 Desactivado")
                    if t["id"] == user["id"]:
                        st.caption("— tu propia cuenta —")
                with c3:
                    if st.button("✏️ Editar", key=f"seleccionar_{t['id']}", use_container_width=True):
                        st.session_state["admin_editando_id"] = t["id"]
                        st.rerun()

        st.divider()
        st.markdown("**➕ Agregar técnico o administrador**")
        st.caption(
            "Con este mismo formulario agregas tanto técnicos como nuevos administradores — marca la "
            "casilla '🔑 Administrador del panel' de abajo si esta persona también debe poder entrar a "
            "Administrador (agregar/editar gente, generar QR, etc.) y a Dashboard. Si ya existe la "
            "cuenta y solo quieres subirla a administrador, selecciónala arriba y usa su pestaña "
            "'⚙️ Permisos', en vez de crear una nueva."
        )
        with st.form("form_nuevo_tecnico", clear_on_submit=True):
            nombre_nuevo = st.text_input("Nombre completo", key="nuevo_nombre")
            username_nuevo = st.text_input("Usuario", key="nuevo_usuario")
            password_nuevo = st.text_input("Contraseña inicial", type="password", key="nuevo_password")
            es_admin_nuevo = st.checkbox(
                "🔑 Administrador del panel (además de atender tickets, puede administrar usuarios)",
                key="nuevo_es_admin",
            )
            correo_nuevo = st.text_input(
                "Correo (opcional, para mandarle la Orden de Trabajo al asignarle un ticket)", key="nuevo_correo",
            )
            accesos_nuevo = st.multiselect(
                "Categorías que atiende (vacío = todas)", CATEGORIAS_TICKET, key="nuevo_accesos",
                help="Un administrador ya ve todo el sistema de todas formas — esto importa sobre todo para técnicos normales.",
            )
            if st.form_submit_button("Crear cuenta", use_container_width=True):
                if not nombre_nuevo.strip() or not username_nuevo.strip() or not password_nuevo:
                    st.error("Completa nombre, usuario y contraseña.")
                else:
                    try:
                        db.create_it_usuario(
                            nombre_nuevo, username_nuevo, password_nuevo,
                            es_admin=es_admin_nuevo, categorias_acceso=accesos_nuevo, correo=correo_nuevo,
                        )
                        st.success(
                            f"'{nombre_nuevo}' agregado "
                            + ("como administrador." if es_admin_nuevo else "al equipo de TI.")
                        )
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

# ---------------------------------------------------------------------------
# 📱 Código QR — uno por empresa, para que los solicitantes accedan más
# fácil al formulario público (ver también app.py: lee "?empresa=...").
# ---------------------------------------------------------------------------
with tab_qr:
    st.caption(
        "Genera un código QR para cada empresa. Al escanearlo, el solicitante llega directo al "
        "formulario público de 'Reportar un problema' con esa empresa ya seleccionada — así no tiene "
        "que escribir el link a mano ni elegir su empresa. Imprímelo o pégalo donde lo necesites (por "
        "ejemplo, en cada tienda/oficina)."
    )

    url_guardada = db.get_url_publica()
    with st.form("form_url_publica"):
        url_input = st.text_input(
            "Link público de esta app (el mismo que ya compartes para reportar problemas)",
            value=url_guardada, placeholder="https://tu-app.streamlit.app",
        )
        if st.form_submit_button("💾 Guardar link", use_container_width=True):
            if not url_input.strip():
                st.error("Escribe el link público de la app.")
            else:
                db.set_url_publica(url_input)
                st.success("Link guardado.")
                st.rerun()

    url_publica = db.get_url_publica()
    if not url_publica:
        st.info("Guarda primero el link público de la app (arriba) para poder generar los códigos QR.")
    else:
        cols_qr = st.columns(len(EMPRESAS_TICKET))
        for col, emp in zip(cols_qr, EMPRESAS_TICKET):
            link_empresa = f"{url_publica}?empresa={quote(emp)}"
            qr_png = generar_qr_png(link_empresa)
            with col:
                st.markdown(f"**{emp}**")
                if qr_png is None:
                    st.error(
                        "Falta instalar la librería 'qrcode' — agrega `qrcode[pil]` a requirements.txt "
                        "y reinicia la app."
                    )
                else:
                    st.image(qr_png, use_container_width=True)
                    st.download_button(
                        "⬇️ Descargar QR", data=qr_png,
                        file_name=f"qr_{emp.lower().replace(' ', '_')}.png", mime="image/png",
                        use_container_width=True, key=f"qr_download_{emp}",
                    )
                st.caption(link_empresa)

# ---------------------------------------------------------------------------
# ✉️ Correos — a quién avisar por correo cuando entra un ticket nuevo, por
# categoría (ver también database.enviar_avisos_ticket_nuevo).
# ---------------------------------------------------------------------------
with tab_correos:
    st.caption(
        "Cada vez que un solicitante reporta un problema, se manda automáticamente un correo (con la "
        "Orden de Trabajo en PDF adjunta) a la lista de abajo (según la categoría del ticket) y, si "
        "el solicitante dejó un correo válido, también se le confirma a él que su ticket quedó "
        "registrado. Cuando después alguien del equipo toma el ticket, se le vuelve a mandar la orden "
        "directo a su correo (el que le pongas en la pestaña 'Usuarios' → editar a cada técnico)."
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
