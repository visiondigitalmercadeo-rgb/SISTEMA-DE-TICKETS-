"""Utilidades chicas — hoy solo el helper para convertir una foto/captura
adjunta a base64 con un límite de tamaño seguro (mismo concepto que
plataforma_ventas: Firestore tiene un límite duro de 1 MiB por documento)."""

import base64


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
