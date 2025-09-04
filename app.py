# ==============================================================
# app.py — Inventario Flask (CRUD + búsqueda) + Persistencia TXT/JSON/CSV
#          + SQLAlchemy (usuarios.db)
# ==============================================================

# 1) IMPORTS BÁSICOS ---------------------------------------------------------
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3, json, csv
from pathlib import Path
from datetime import datetime

# 2) CONFIGURACIÓN DE FLASK --------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "cambia_esta_clave_super_secreta"  # CSRF para formularios

# 3) BASES DE DATOS (sqlite3 para Productos) --------------------------------
DB_PATH = "inventario.db"   # dejamos tu inventario donde ya lo tienes

def get_conn():
    """Devuelve una conexión SQLite con filas tipo dict (Row)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea la tabla productos si no existe."""
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS productos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            cantidad INTEGER NOT NULL CHECK(cantidad>=0),
            precio REAL NOT NULL CHECK(precio>=0)
        )""")
        conn.commit()

# 4) PERSISTENCIA CON ARCHIVOS ----------------------------------------------
BASE_DIR = Path(__file__).parent
DATOS_DIR = BASE_DIR / "datos"
DATOS_DIR.mkdir(exist_ok=True)

# 4.1) Helpers genéricos para parseo seguro
def _as_int(v, default=1):
    try: return int(v)
    except (TypeError, ValueError): return default

def _as_float(v, default=1.0):
    try: return float(str(v).replace(",", "."))
    except (TypeError, ValueError): return default

# 4.2) TXT -------------------------------------------------------------------
TXT_PATH = DATOS_DIR / "datos.txt"

@app.route("/txt/guardar")
def guardar_txt():
    """
    Guarda una línea en datos.txt:
      /txt/guardar?nombre=Pan&cantidad=3&precio=2.5
    """
    nombre   = (request.args.get("nombre") or "Producto TXT").strip()
    cantidad = _as_int(request.args.get("cantidad"), 1)
    precio   = _as_float(request.args.get("precio"), 1.0)
    fecha    = datetime.now().isoformat(timespec="seconds")
    linea = f"{fecha} | {nombre} | {cantidad} | {precio:.2f}\n"
    with open(TXT_PATH, "a", encoding="utf-8") as f:
        f.write(linea)
    return f"OK TXT → {linea}"

@app.route("/txt/ver")
def ver_txt():
    contenido = TXT_PATH.read_text(encoding="utf-8") if TXT_PATH.exists() else "(archivo vacío)"
    return f"<pre>{contenido}</pre>"

# 4.3) JSON ------------------------------------------------------------------
JSON_PATH = DATOS_DIR / "datos.json"

def _json_load():
    if JSON_PATH.exists():
        try: return json.loads(JSON_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError: return []
    return []

def _json_save(data):
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

@app.route("/json/guardar")
def guardar_json():
    """
    Agrega un objeto al arreglo JSON:
      /json/guardar?nombre=Leche&cantidad=2&precio=3.4
    """
    nombre   = (request.args.get("nombre") or "Producto JSON").strip()
    cantidad = _as_int(request.args.get("cantidad"), 1)
    precio   = _as_float(request.args.get("precio"), 1.0)
    fecha    = datetime.now().isoformat(timespec="seconds")
    data = _json_load()
    data.append({"fecha": fecha, "nombre": nombre, "cantidad": cantidad, "precio": precio})
    _json_save(data)
    return {"ok": True, "total_registros": len(data)}

@app.route("/json/ver")
def ver_json():
    data = _json_load()
    return f"<pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre>"

# 4.4) CSV -------------------------------------------------------------------
CSV_PATH = DATOS_DIR / "datos.csv"

@app.route("/csv/guardar")
def guardar_csv():
    """
    Agrega una fila al CSV (crea encabezado si no existe):
      /csv/guardar?nombre=Azucar&cantidad=5&precio=4.2
    """
    nombre   = (request.args.get("nombre") or "Producto CSV").strip()
    cantidad = _as_int(request.args.get("cantidad"), 1)
    precio   = _as_float(request.args.get("precio"), 1.0)
    fecha    = datetime.now().isoformat(timespec="seconds")

    write_header = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["fecha", "nombre", "cantidad", "precio"])
        if write_header: w.writeheader()
        w.writerow({"fecha": fecha, "nombre": nombre, "cantidad": cantidad, "precio": f"{precio:.2f}"})
    return {"ok": True}

@app.route("/csv/ver")
def ver_csv():
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        return "<pre>(archivo vacío)</pre>"
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return f"<pre>{json.dumps(rows, ensure_ascii=False, indent=2)}</pre>"

# 5) FORMULARIOS (Flask-WTF) -------------------------------------------------
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

class ProductoForm(FlaskForm):
    nombre   = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=50)])
    cantidad = IntegerField("Cantidad", validators=[DataRequired(), NumberRange(min=0)])
    precio   = DecimalField("Precio", places=2, validators=[DataRequired(), NumberRange(min=0)])
    enviar   = SubmitField("Guardar")

class DeleteForm(FlaskForm):
    enviar = SubmitField("Eliminar")

# 6) RUTAS (CRUD + BÚSQUEDA) -------------------------------------------------
@app.route("/")
def home():
    with get_conn() as conn:
        filas = conn.execute("SELECT id,nombre,cantidad,precio FROM productos ORDER BY id").fetchall()
    total_items = sum(p["cantidad"] for p in filas)
    total_valor = sum(p["cantidad"] * p["precio"] for p in filas)
    return render_template("index.html",
                           productos=filas, delete_form=DeleteForm(),
                           total_items=total_items, total_valor=total_valor,
                           titulo="Inventario")

@app.route("/nuevo/", methods=["GET","POST"])
def nuevo():
    form = ProductoForm()
    if form.validate_on_submit():
        with get_conn() as conn:
            conn.execute("INSERT INTO productos(nombre,cantidad,precio) VALUES (?,?,?)",
                         (form.nombre.data.strip(), int(form.cantidad.data), float(form.precio.data)))
            conn.commit()
        flash("Producto creado.", "success")
        return redirect(url_for("home"))
    return render_template("product_form.html", form=form, titulo="Nuevo producto")

@app.route("/editar/<int:pid>/", methods=["GET","POST"])
def editar(pid: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM productos WHERE id=?", (pid,)).fetchone()
    if row is None:
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("home"))

    form = ProductoForm()
    if request.method == "GET":
        form.nombre.data = row["nombre"]; form.cantidad.data = row["cantidad"]; form.precio.data = row["precio"]
    if form.validate_on_submit():
        with get_conn() as conn:
            conn.execute("UPDATE productos SET nombre=?,cantidad=?,precio=? WHERE id=?",
                         (form.nombre.data.strip(), int(form.cantidad.data), float(form.precio.data), pid))
            conn.commit()
        flash("Producto actualizado.", "success")
        return redirect(url_for("home"))
    return render_template("product_form.html", form=form, titulo=f"Editar (ID {pid})")

@app.route("/eliminar/<int:pid>/", methods=["POST"])
def eliminar(pid: int):
    form = DeleteForm()
    if form.validate_on_submit():
        with get_conn() as conn:
            conn.execute("DELETE FROM productos WHERE id=?", (pid,))
            conn.commit()
        flash(f"Producto ID {pid} eliminado.", "info")
    else:
        flash("Solicitud inválida.", "warning")
    return redirect(url_for("home"))

@app.route("/buscar")
def buscar():
    q = (request.args.get("q") or "").strip().lower()
    with get_conn() as conn:
        filas = conn.execute("SELECT * FROM productos ORDER BY id").fetchall()
    resultados = [p for p in filas if q in p["nombre"].lower()] if q else []
    total_items = sum(p["cantidad"] for p in resultados)
    total_valor = sum(p["cantidad"] * p["precio"] for p in resultados)
    return render_template("index.html",
                           productos=resultados, delete_form=DeleteForm(),
                           total_items=total_items, total_valor=total_valor,
                           q=q, titulo="Inventario")

# 7) SQLALCHEMY (usuarios.db en /database) -----------------------------------
#    Pequeña demo ORM: crear y listar usuarios
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker

DB_DIR = (BASE_DIR / "database"); DB_DIR.mkdir(exist_ok=True)
ENGINE = create_engine(f"sqlite:///{DB_DIR/'usuarios.db'}", echo=False, future=True)
Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id     = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False)
    email  = Column(String(120), nullable=False)

Base.metadata.create_all(ENGINE)
Session = sessionmaker(bind=ENGINE, expire_on_commit=False)

@app.route("/usuarios/crear")
def usuarios_crear():
    """
    Crea un usuario rápido con querystrings:
      /usuarios/crear?nombre=Ariel&email=ariel@mail.com
    """
    nombre = (request.args.get("nombre") or "Usuario Demo").strip()
    email  = (request.args.get("email") or "demo@mail.com").strip()
    with Session() as s:
        s.add(Usuario(nombre=nombre, email=email))
        s.commit()
    return {"ok": True, "mensaje": f"Usuario '{nombre}' creado"}

@app.route("/usuarios/listar")
def usuarios_listar():
    """Devuelve los usuarios almacenados con SQLAlchemy (usuarios.db)."""
    with Session() as s:
        users = s.query(Usuario).order_by(Usuario.id).all()
    data = [{"id": u.id, "nombre": u.nombre, "email": u.email} for u in users]
    return f"<pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre>"

# 8) PUNTO DE ENTRADA --------------------------------------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
