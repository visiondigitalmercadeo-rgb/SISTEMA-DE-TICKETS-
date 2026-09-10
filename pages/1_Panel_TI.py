
import streamlit as st

import auth
import database as db
from config import CATEGORIAS_TICKET, EMPRESA_NOMBRE, ESTADO_EMOJI, ESTADOS_TICKET, FAVICON_PATH, TICKET_SIGUIENTE_ESTADO

st.set_page_config(page_title=f"Panel TI — {EMPRESA_NOMBRE}", page_icon=FAVICON_PATH, layout="wide")

if not auth.require_login():
    st.stop()

user = auth.current_user()

with st.sidebar:
    st.markdown(f"**{user['nombre']}**")
    st.caption("Administrador" if user["es_admin"] else "Técnico")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        auth.do_logout()
        st.rerun()

st.title("🛠️ Panel de Soporte TI")
st.caption("Tablero de tickets — arrástralos mentalmente de izquierda a derecha conforme avanzan.")

# ---------------------------------------------------------------------------
# Gestión de técnicos (solo administradores del panel)
# ---------------------------------------------------------------------------
if user["es_admin"]:
    with st.expander("⚙️ Gestión de técnicos del equipo de TI"):
        tecnicos = db.list_it_usuarios()
        if tecnicos:
            for t in tecnicos:
                c1, c2, c3 = st.columns([3, 2, 2])
                c1.markdown(f"**{t['nombre']}** ({t['username']})" + (" · admin" if t.get("es_admin") else ""))
                c2.caption("Activo" if t.get("activo", True) else "Desactivado")
                if t["id"] != user["id"]:
                    etiqueta_toggle = "Desactivar" if t.get("activo", True) else "Reactivar"
                    if c3.button(etiqueta_toggle, key=f"toggle_tec_{t['id']}"):
                        db.set_it_usuario_activo(t["id"], not t.get("activo", True))
                        st.rerun()

        st.markdown("**➕ Agregar técnico**")
        with st.form("form_nuevo_tecnico", clear_on_submit=True):
            nombre_nuevo = st.text_input("Nombre completo")
            username_nuevo = st.text_input("Usuario")
            password_nuevo = st.text_input("Contraseña inicial", type="password")
            es_admin_nuevo = st.checkbox("También administrador del panel (puede agregar/quitar técnicos)")
            if st.form_submit_button("Crear técnico", use_container_width=True):
                if not nombre_nuevo.strip() or not username_nuevo.strip() or not password_nuevo:
                    st.error("Completa nombre, usuario y contraseña.")
                else:
                    try:
                        db.create_it_usuario(nombre_nuevo, username_nuevo, password_nuevo, es_admin=es_admin_nuevo)
                        st.success(f"'{nombre_nuevo}' agregado al equipo de TI.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

st.divider()

# ---------------------------------------------------------------------------
# Filtro por categoría + tablero
# ---------------------------------------------------------------------------
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
                st.caption(f"{t['categoria']} · {t.get('area') or '—'}")
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

                # Asignar / reasignar técnico.
                if tecnicos_activos:
                    opciones_tec = {"— Sin asignar —": None}
                    opciones_tec.update({tec["nombre"]: tec["id"] for tec in tecnicos_activos})
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
