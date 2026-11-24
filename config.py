# config.py
# Parámetros de configuración para la conexión a MySQL (proyect_db)
# Las credenciales se cargan exclusivamente desde variables de entorno (.env).

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PORT_RAW = (os.environ.get("DB_PORT") or "").strip()
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(DB_PORT_RAW or "3306"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "proyect_db"),
    "charset": "utf8mb4",
}

DB_SSL_ENABLED = os.environ.get("DB_SSL", "0").strip().lower() in ("1", "true", "yes", "on")
DB_SSL_CA = os.environ.get("DB_SSL_CA", "").strip()
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()

_CLAVES_INSEGURAS = {
    "",
    "cambia-esta-clave-secreta-en-produccion",
    "polo-norte-clave-temporal-local",
}
_SECRET_ENV = (os.environ.get("SESSION_SECRET") or "").strip()
if APP_ENV == "production" and (_SECRET_ENV in _CLAVES_INSEGURAS or len(_SECRET_ENV) < 16):
    raise RuntimeError(
        "SESSION_SECRET inválido o faltante para entorno de producción (mínimo 16 caracteres)."
    )
SESSION_SECRET = _SECRET_ENV or "polo-norte-clave-temporal-local"
