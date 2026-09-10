from datetime import datetime

import streamlit as st

import auth
import database as db
from config import CATEGORIAS_TICKET, EMPRESA_NOMBRE, EMPRESAS_TICKET, FAVICON_PATH, MESES_ES
from utils import formatear_horas

st.set_page_config(page_title=f"Dashboard — {EMPRESA_NOMBRE}", page_icon=FAVICON_PATH, layout="wide")
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

st.title("📊 Dashboard")

if not user["es_admin"]:
    st.error("Esta sección es solo para administradores. Pide a un administrador que te dé acceso si lo necesitas.")
    st.stop()

st.caption("KPIs de todo el sistema — filtra por mes, tipo de solicitud y empresa.")

todos = db.list_tickets()

ahora = datetime.now()
anios_disponibles = sorted(
    {ahora.year} | {
        datetime.fromisoformat(t["creado_en"]).year
        for t in todos if t.get("creado_en")
    },
    reverse=True,
)

col_mes, col_anio, col_tipo, col_empresa = st.columns(4)
with col_mes:
    mes_sel = st.selectbox("Mes", MESES_ES, index=ahora.month - 1, key="dash_filtro_mes")
with col_anio:
    anio_sel = st.selectbox(
        "Año", anios_disponibles,
        index=anios_disponibles.index(ahora.year) if ahora.year in anios_disponibles else 0,
        key="dash_filtro_anio",
    )
with col_tipo:
    tipo_sel = st.selectbox("Tipo", ["Todos"] + CATEGORIAS_TICKET, key="dash_filtro_tipo")
with col_empresa:
    empresa_sel = st.selectbox("Empresa", ["Todas"] + EMPRESAS_TICKET, key="dash_filtro_empresa")

mes_num = MESES_ES.index(mes_sel) + 1
categoria_filtro = None if tipo_sel == "Todos" else tipo_sel
empresa_filtro = None if empresa_sel == "Todas" else empresa_sel

kpis = db.calcular_kpis_dashboard(todos, anio_sel, mes_num, categoria=categoria_filtro, empresa=empresa_filtro)

st.divider()

st.markdown(f"##### 📅 {mes_sel} {anio_sel}" + (f" · {tipo_sel}" if categoria_filtro else "") + (f" · {empresa_sel}" if empresa_filtro else ""))
c1, c2, c3 = st.columns(3)
c1.metric("🆕 Tickets creados", kpis["creados"])
c2.metric("✅ Tickets cerrados", kpis["cerrados"])
c3.metric("⏱️ Tiempo promedio de resolución", formatear_horas(kpis["horas_promedio_resolucion"]))

st.divider()

if tipo_sel == "Todos":
    st.markdown("##### Por tipo de solicitud")
    cols_tipo = st.columns(len(CATEGORIAS_TICKET))
    for col, cat in zip(cols_tipo, CATEGORIAS_TICKET):
        with col:
            st.metric(f"{cat} — creados", kpis["por_categoria_creados"].get(cat, 0))
            st.metric(f"{cat} — cerrados", kpis["por_categoria_cerrados"].get(cat, 0))
    st.divider()

if empresa_sel == "Todas":
    st.markdown("##### Por empresa")
    cols_empresa = st.columns(len(EMPRESAS_TICKET))
    for col, emp in zip(cols_empresa, EMPRESAS_TICKET):
        with col:
            st.metric(f"{emp} — creados", kpis["por_empresa_creados"].get(emp, 0))
            st.metric(f"{emp} — cerrados", kpis["por_empresa_cerrados"].get(emp, 0))
