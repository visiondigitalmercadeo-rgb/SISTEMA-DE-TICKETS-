"""Login del equipo de TI — sistema aparte del de plataforma_ventas (usuario/
contraseña propios, guardados en la colección "it_usuarios"). Sin roles
finos: cualquier técnico activo puede atender cualquier ticket; "es_admin"
solo controla quién puede agregar/desactivar compañeros del equipo (ver
pages/1_Panel_TI.py)."""

import streamlit as st

import database as db
from config import EMPRESA_NOMBRE, LOGO_PATH


def current_user():
    return st.session_state.get("it_user")


def do_login(username: str, password: str) -> bool:
    user = db.get_it_usuario_by_username(username)
    if not user or not user.get("activo", True):
        return False
    if not db.check_password(password, user["password_hash"]):
        return False
    st.session_state["it_user"] = {
        "id": user["id"], "nombre": user["nombre"], "username": user["username"],
        "es_admin": bool(user.get("es_admin")),
    }
    return True


def do_logout():
    st.session_state.pop("it_user", None)


def _logo_centrado(path, width):
    import base64
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        st.markdown(
            f"<div style='text-align:center;'><img src='data:image/png;base64,{b64}' width='{width}' /></div>",
            unsafe_allow_html=True,
        )
    except Exception:
        st.image(path, width=width)


def require_login() -> bool:
    """Muestra el formulario de login (o, si todavía no existe ningún
    técnico, el formulario de 'primer arranque' para crear al primero) si no
    hay sesión activa. Debe llamarse al inicio de pages/1_Panel_TI.py.
    Devuelve True si hay un usuario autenticado."""
    if current_user():
        return True

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        _logo_centrado(LOGO_PATH, 260)
        st.markdown(
            f"<h3 style='text-align:center;margin-top:0.5rem;'>{EMPRESA_NOMBRE} · Soporte TI</h3>",
            unsafe_allow_html=True,
        )

        tecnicos_existentes = db.list_it_usuarios()
        if not tecnicos_existentes:
            st.info(
                "👋 Todavía no hay ningún técnico registrado — crea la primera cuenta del equipo de "
                "TI (queda como administrador del panel, para poder agregar a los demás compañeros "
                "después)."
            )
            with st.form("form_primer_tecnico"):
                nombre_0 = st.text_input("Tu nombre completo")
                username_0 = st.text_input("Usuario (sin espacios, ej. jperez)")
                password_0 = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Crear mi cuenta y entrar", use_container_width=True):
                    if not nombre_0.strip() or not username_0.strip() or not password_0:
                        st.error("Completa nombre, usuario y contraseña.")
                    else:
                        try:
                            db.create_it_usuario(nombre_0, username_0, password_0, es_admin=True)
                            if do_login(username_0, password_0):
                                st.rerun()
                        except ValueError as e:
                            st.error(str(e))
            return False

        with st.form("form_login_it"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Iniciar sesión", use_container_width=True):
                if do_login(username, password):
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos, o la cuenta está desactivada.")
    return False
