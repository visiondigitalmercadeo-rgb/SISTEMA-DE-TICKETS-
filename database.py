"""Capa de datos — Firestore, con un 'modo de práctica' automático en
memoria mientras todavía no hay credenciales de Firebase configuradas
(idéntico concepto al de la plataforma comercial plataforma_ventas).

IMPORTANTE: este sistema usa el MISMO proyecto de Firebase que
plataforma_ventas (las mismas credenciales que ya están en los secretos de
Streamlit Cloud) — pero todas las colecciones de aquí llevan el prefijo
"it_" para que nunca se mezclen con los datos comerciales.

Todo el resto de la app (app.py, pages/*.py) llama únicamente a las
funciones de este archivo — nunca usa Firestore directamente.
"""

import os
from datetime import datetime

import bcrypt
import firebase_admin
from firebase_admin import credentials, firestore

import fake_firestore
from config import BASE_DIR

SERVICE_ACCOUNT_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

_client = None
MODO_PRACTICA = False


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Conexión a Firestore (o modo de práctica en memoria)
# ---------------------------------------------------------------------------
def _cargar_credenciales():
    try:
        import streamlit as st
        if "firebase" in st.secrets:
            return credentials.Certificate(dict(st.secrets["firebase"]))
    except Exception as e:
        import traceback
        print("ERROR AL CARGAR CREDENCIALES DE FIREBASE:", e)
        traceback.print_exc()

    if os.path.exists(SERVICE_ACCOUNT_PATH):
        return credentials.Certificate(SERVICE_ACCOUNT_PATH)

    return None


def get_client():
    """Devuelve el cliente de Firestore (real o de práctica), creándolo la
    primera vez que se necesita y reutilizándolo en el resto de la sesión.
    Usa una app de firebase_admin aparte ("soporte_ti") para no chocar si
    algún día este proceso comparte memoria con el de plataforma_ventas."""
    global _client, MODO_PRACTICA
    if _client is not None:
        return _client

    cred = _cargar_credenciales()
    if cred is not None:
        try:
            app_fb = firebase_admin.get_app("soporte_ti")
        except ValueError:
            app_fb = firebase_admin.initialize_app(cred, name="soporte_ti")
        # Mismo ajuste que plataforma_ventas: el proyecto apunta a la base de
        # datos "vision-digital-ventas-2" (no la "(default)") — ver la nota
        # equivalente en el database.py de plataforma_ventas.
        _client = firestore.client(app=app_fb, database_id="vision-digital-ventas-2")
        MODO_PRACTICA = False
    else:
        _client = fake_firestore.FakeFirestoreClient()
        MODO_PRACTICA = True
    return _client


def firebase_conectado() -> bool:
    get_client()
    return not MODO_PRACTICA


def _doc_to_dict(snap):
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data["id"] = snap.id
    return data


# ---------------------------------------------------------------------------
# Usuarios de soporte (equipo de TI) — colección "it_usuarios". Es un login
# aparte del de plataforma_ventas: usuario/contraseña propios, sin roles
# finos (todos pueden atender tickets); "es_admin" solo controla quién puede
# agregar/desactivar compañeros del equipo (ver pages/1_Panel_TI.py).
# ---------------------------------------------------------------------------
def list_it_usuarios(solo_activos=False):
    rows = [_doc_to_dict(s) for s in get_client().collection("it_usuarios").stream()]
    if solo_activos:
        rows = [r for r in rows if r.get("activo", True)]
    rows.sort(key=lambda r: (r.get("nombre") or "").lower())
    return rows


def get_it_usuario(uid):
    snap = get_client().collection("it_usuarios").document(uid).get()
    return _doc_to_dict(snap)


def get_it_usuario_by_username(username):
    username = (username or "").strip().lower()
    if not username:
        return None
    query = get_client().collection("it_usuarios").where("username", "==", username).limit(1)
    for snap in query.stream():
        return _doc_to_dict(snap)
    return None


def create_it_usuario(nombre, username, password, es_admin=False, categorias_acceso=None):
    username = username.strip().lower()
    if get_it_usuario_by_username(username):
        raise ValueError(f"Ya existe un usuario de TI con el nombre de usuario '{username}'.")
    doc_ref = get_client().collection("it_usuarios").document()
    doc_ref.set({
        "nombre": nombre.strip(), "username": username, "password_hash": hash_password(password),
        "es_admin": bool(es_admin), "activo": True,
        "categorias_acceso": list(categorias_acceso) if categorias_acceso else [],
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    })
    return doc_ref.id


def set_it_usuario_activo(uid, activo):
    if not activo:
        _validar_no_es_ultimo_admin_activo(uid, motivo="desactivar")
    get_client().collection("it_usuarios").document(uid).update({"activo": bool(activo)})


def update_it_usuario_password(uid, password):
    get_client().collection("it_usuarios").document(uid).update({"password_hash": hash_password(password)})


def _admins_activos(excluir_uid=None):
    """Lista de administradores activos, opcionalmente excluyendo un uid
    (para poder preguntar '¿si le quito el admin a este, queda alguien más
    como administrador?')."""
    return [
        u for u in list_it_usuarios(solo_activos=True)
        if u.get("es_admin") and u["id"] != excluir_uid
    ]


def _validar_no_es_ultimo_admin_activo(uid, motivo):
    """Evita dejar el sistema sin ningún administrador activo (nadie podría
    volver a gestionar el equipo). 'motivo' se usa solo para el mensaje de
    error (p. ej. 'quitar el admin a', 'desactivar', 'eliminar')."""
    usuario = get_it_usuario(uid)
    if not usuario or not usuario.get("es_admin") or not usuario.get("activo", True):
        return  # no era admin activo, no hay riesgo de dejar el equipo sin administrador
    if not _admins_activos(excluir_uid=uid):
        raise ValueError(
            f"No puedes {motivo} a '{usuario.get('nombre')}': es el único administrador activo. "
            "Primero vuelve administrador a otro técnico."
        )


def update_it_usuario_perfil(uid, nombre, username, categorias_acceso=None):
    """Edita nombre, usuario (login) y las categorías de tickets que puede
    atender. No toca contraseña, rol ni estado activo/inactivo (ver las
    funciones dedicadas para eso)."""
    nombre = (nombre or "").strip()
    username = (username or "").strip().lower()
    if not nombre or not username:
        raise ValueError("El nombre y el usuario no pueden quedar vacíos.")
    existente = get_it_usuario_by_username(username)
    if existente and existente["id"] != uid:
        raise ValueError(f"Ya existe otro usuario de TI con el nombre de usuario '{username}'.")
    get_client().collection("it_usuarios").document(uid).update({
        "nombre": nombre, "username": username,
        "categorias_acceso": list(categorias_acceso) if categorias_acceso else [],
    })


def set_it_usuario_admin(uid, es_admin):
    """Sube o quita el permiso de administrador. No deja quitarle el admin
    al único administrador activo que queda."""
    if not es_admin:
        _validar_no_es_ultimo_admin_activo(uid, motivo="quitarle el admin")
    get_client().collection("it_usuarios").document(uid).update({"es_admin": bool(es_admin)})


def delete_it_usuario(uid):
    """Elimina permanentemente a un usuario de TI (no solo desactivarlo). Los
    tickets que haya tenido asignados conservan el nombre en su historial,
    así que no se pierde la trazabilidad. No deja eliminar al único
    administrador activo que queda."""
    _validar_no_es_ultimo_admin_activo(uid, motivo="eliminar")
    get_client().collection("it_usuarios").document(uid).delete()


# ---------------------------------------------------------------------------
# Tickets — colección "it_tickets". Numeración corrida (TI-0001, TI-0002,
# ...), con un "historial" que va guardando cada cambio de estado y cada
# comentario de seguimiento, para tener trazabilidad completa del ticket.
# ---------------------------------------------------------------------------
def _siguiente_numero_ticket():
    rows = [_doc_to_dict(s) for s in get_client().collection("it_tickets").stream()]
    numeros = [r.get("numero") for r in rows if isinstance(r.get("numero"), int)]
    return (max(numeros, default=0)) + 1


def list_tickets(estado=None, categoria=None):
    client = get_client()
    query = client.collection("it_tickets")
    if estado:
        query = query.where("estado", "==", estado)
    if categoria:
        query = query.where("categoria", "==", categoria)
    rows = [_doc_to_dict(s) for s in query.stream()]
    rows.sort(key=lambda r: r.get("numero") or 0, reverse=True)
    return rows


def get_ticket(ticket_id):
    snap = get_client().collection("it_tickets").document(ticket_id).get()
    return _doc_to_dict(snap)


def get_ticket_por_numero(numero: int):
    query = get_client().collection("it_tickets").where("numero", "==", numero).limit(1)
    for snap in query.stream():
        return _doc_to_dict(snap)
    return None


def create_ticket(nombre_solicitante, contacto, area, categoria, descripcion, foto_b64=None, foto_nombre=None, foto_tipo=None):
    numero = _siguiente_numero_ticket()
    ahora = datetime.now().isoformat(timespec="seconds")
    doc_ref = get_client().collection("it_tickets").document()
    doc_ref.set({
        "numero": numero,
        "nombre_solicitante": (nombre_solicitante or "").strip(),
        "contacto": (contacto or "").strip() or None,
        "area": (area or "").strip() or None,
        "categoria": categoria,
        "descripcion": (descripcion or "").strip(),
        "foto_b64": foto_b64, "foto_nombre": foto_nombre, "foto_tipo": foto_tipo,
        "estado": "Nuevo",
        "asignado_a_id": None, "asignado_a_nombre": None,
        "historial": [{"tipo": "creado", "detalle": "Ticket creado por el solicitante", "fecha": ahora}],
        "creado_en": ahora,
    })
    return numero


def asignar_ticket(ticket_id, tecnico_id, tecnico_nombre, autor_nombre=None):
    ahora = datetime.now().isoformat(timespec="seconds")
    ticket = get_ticket(ticket_id)
    historial = (ticket or {}).get("historial") or []
    detalle = f"Asignado a {tecnico_nombre}" if tecnico_nombre else "Se quitó la asignación (sin técnico)"
    historial.append({"tipo": "asignado", "detalle": detalle, "autor": autor_nombre, "fecha": ahora})
    cambios = {"asignado_a_id": tecnico_id, "asignado_a_nombre": tecnico_nombre, "historial": historial}
    if tecnico_nombre and (ticket or {}).get("estado") == "Nuevo":
        cambios["estado"] = "Asignado"
    get_client().collection("it_tickets").document(ticket_id).update(cambios)


def avanzar_ticket(ticket_id, nuevo_estado, autor_nombre=None):
    ahora = datetime.now().isoformat(timespec="seconds")
    ticket = get_ticket(ticket_id)
    historial = (ticket or {}).get("historial") or []
    historial.append({
        "tipo": "estado", "detalle": f"Pasó a '{nuevo_estado}'", "autor": autor_nombre, "fecha": ahora,
    })
    get_client().collection("it_tickets").document(ticket_id).update({"estado": nuevo_estado, "historial": historial})


def reclasificar_ticket(ticket_id, nueva_categoria, autor_nombre=None):
    ahora = datetime.now().isoformat(timespec="seconds")
    ticket = get_ticket(ticket_id)
    historial = (ticket or {}).get("historial") or []
    historial.append({
        "tipo": "categoria", "detalle": f"Reclasificado como '{nueva_categoria}'", "autor": autor_nombre, "fecha": ahora,
    })
    get_client().collection("it_tickets").document(ticket_id).update({"categoria": nueva_categoria, "historial": historial})


def agregar_comentario_ticket(ticket_id, autor_nombre, comentario):
    if not (comentario or "").strip():
        return
    ahora = datetime.now().isoformat(timespec="seconds")
    ticket = get_ticket(ticket_id)
    historial = (ticket or {}).get("historial") or []
    historial.append({
        "tipo": "comentario", "detalle": comentario.strip(), "autor": autor_nombre, "fecha": ahora,
    })
    get_client().collection("it_tickets").document(ticket_id).update({"historial": historial})
