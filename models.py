# models.py
# Capa de acceso de usuarios para Flask-Login usando MySQL (XAMPP)
from typing import Optional, Dict, Any
from werkzeug.security import generate_password_hash
from Conexion import get_db_connection
from flask_login import UserMixin

# ---- Objeto de sesión para Flask-Login ----
class User(UserMixin):
    def __init__(self, id: int, nombre: str, email: str):
        self.id = str(id)          # Flask-Login espera string
        self.nombre = nombre
        self.email = email

# ---- Helpers a MySQL ----
def _fetch_one(sql: str, params=()) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def _execute(sql: str, params=()) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    cur.close(); conn.close()

# ---- API pública usada por app.py ----
def get_user_by_id(user_id: int) -> Optional[User]:
    row = _fetch_one("SELECT id, nombre, email FROM usuarios WHERE id=%s", (user_id,))
    return User(row["id"], row["nombre"], row["email"]) if row else None

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Devuelve dict con id, nombre, email, password_hash o None."""
    return _fetch_one(
        "SELECT id, nombre, email, password_hash FROM usuarios WHERE email=%s",
        (email,)
    )

def create_user(nombre: str, email: str, password: str) -> None:
    password_hash = generate_password_hash(password)
    _execute(
        "INSERT INTO usuarios (nombre, email, password_hash) VALUES (%s, %s, %s)",
        (nombre, email, password_hash),
    )
