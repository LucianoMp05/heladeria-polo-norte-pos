# conexion.py
# Módulo encargado de gestionar la conexión y desconexión con MySQL mediante PyMySQL
# Soporta conexión local y conexión segura TLS/SSL en la nube (Azure MySQL Flexible Server).

import ssl
import sys
sys.dont_write_bytecode = True

import pymysql
from pymysql.err import MySQLError as Error
from config import DB_CONFIG, DB_SSL_ENABLED, DB_SSL_CA

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _construir_ssl_context():
    """Retorna un SSLContext configurado si TLS está habilitado para MySQL Cloud."""
    if not DB_SSL_ENABLED and not DB_SSL_CA:
        return None
    if DB_SSL_CA:
        return ssl.create_default_context(cafile=DB_SSL_CA)
    ctx = ssl.create_default_context()
    return ctx


def obtener_conexion():
    """
    Establece y retorna una conexión activa hacia la base de datos MySQL
    utilizando PyMySQL y los parámetros cargados desde variables de entorno.
    """
    try:
        params = dict(DB_CONFIG)
        params.setdefault("connect_timeout", 10)
        ssl_ctx = _construir_ssl_context()
        if ssl_ctx is not None:
            params["ssl"] = ssl_ctx
        conexion = pymysql.connect(**params)
        if conexion.open:
            return conexion
    except Error as e:
        print(f"[ERROR DE CONEXIÓN] No se pudo conectar a MySQL con PyMySQL: {e}")
        return None
    except Exception as e:
        print(f"[ERROR DE CONEXIÓN] Error inesperado al abrir conexión MySQL: {e}")
        return None


def cerrar_conexion(conexion, cursor=None):
    """Cierra de forma segura el cursor y la conexión activa con MySQL."""
    try:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.open:
            conexion.close()
    except Error as e:
        print(f"[ERROR AL CERRAR] Ocurrió un problema cerrando la conexión: {e}")


def probar_conexion():
    """
    Diagnóstico del enlace con MySQL mediante PyMySQL invocando Stored Procedures
    de proyect_db (sin consultas SQL directas en Python).
    """
    conexion = obtener_conexion()
    if not conexion:
        return False, "No se pudo establecer conexión con el servidor de datos."
    cursor = None
    try:
        cursor = conexion.cursor()
        info_servidor = conexion.get_server_info()
        cursor.callproc("sp_listar_sucursales")
        sedes = cursor.fetchall()
        return True, f"Conectado a {DB_CONFIG['database']} (MySQL {info_servidor}) — {len(sedes)} sucursales activas"
    except Error as e:
        print(f"[ERROR probar_conexion]: {e}")
        return False, "No se pudo verificar el estado del sistema."
    finally:
        cerrar_conexion(conexion, cursor)


if __name__ == "__main__":
    ok, msg = probar_conexion()
    print(f"[{'OK' if ok else 'FALLO'}] {msg}")
