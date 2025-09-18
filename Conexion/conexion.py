# Conexion/conexion.py
import mysql.connector

def get_db_connection():
    """
    Conecta a MySQL (XAMPP). Ajusta si tu contraseña de root no es vacía.
    DB usada: desarrollo_web
    """
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="",          # pon tu clave si usas
        database="desarrollo_web",
        port=3306
    )
