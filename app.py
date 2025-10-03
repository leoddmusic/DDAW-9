# ==============================================================
# app.py — Inventario Flask (CRUD + búsqueda) + Persistencia TXT/JSON/CSV
#          + SQLAlchemy (usuarios.db) + MySQL (usuarios en XAMPP)
#          + Autenticación con Flask-Login (MySQL)
#          + CRUD MySQL de productos (añadido)
# ==============================================================

from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3, json, csv
from pathlib import Path
from datetime import datetime

# Conexión MySQL
from Conexion import get_db_connection

# Login
from flask_login import (
    LoginManager, login_user, login_required, logout_user, current_user
)
from werkzeug.security import check_password_hash

# Capa de usuarios MySQL
from models import User, get_user_by_id, get_user_by_email, create_user

# Formularios
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Length, NumberRange, Email

app = Flask(__name__)
app.config["SECRET_KEY"] = "cambia_esta_clave_super_secreta"

# ---------------------- LoginManager ---------------------------
login_manager = LoginManager(app)
login_manager.login_view = "auth_login"              # endpoint de la vista de login
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id: str):
    # Recibe id como string -> devuelve User o None
    return get_user_by_id(int(user_id))

# ---------------------- SQLITE (productos) ----------------------
DB_PATH = "inventario.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS productos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            cantidad INTEGER NOT NULL CHECK(cantidad>=0),
            precio REAL NOT NULL CHECK(precio>=0)
        )""")
        conn.commit()

# ---------------------- Archivos de datos -----------------------
BASE_DIR = Path(__file__).parent
DATOS_DIR = BASE_DIR / "datos"
DATOS_DIR.mkdir(exist_ok=True)

def _as_int(v, default=1):
    try: return int(v)
    except (TypeError, ValueError): return default

def _as_float(v, default=1.0):
    try: return float(str(v).replace(",", "."))
    except (TypeError, ValueError): return default

TXT_PATH = DATOS_DIR / "datos.txt"

@app.route("/txt/guardar")
@login_required
def guardar_txt():
    nombre   = (request.args.get("nombre") or "Producto TXT").strip()
    cantidad = _as_int(request.args.get("cantidad"), 1)
    precio   = _as_float(request.args.get("precio"), 1.0)
    fecha    = datetime.now().isoformat(timespec="seconds")
    linea = f"{fecha} | {nombre} | {cantidad} | {precio:.2f}\n"
    with open(TXT_PATH, "a", encoding="utf-8") as f:
        f.write(linea)
    return f"OK TXT → {linea}"

@app.route("/txt/ver")
@login_required
def ver_txt():
    contenido = TXT_PATH.read_text(encoding="utf-8") if TXT_PATH.exists() else "(archivo vacío)"
    return f"<pre>{contenido}</pre>"

JSON_PATH = DATOS_DIR / "datos.json"

def _json_load():
    if JSON_PATH.exists():
        try: return json.loads(JSON_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError: return []
    return []

def _json_save(data):
    JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

@app.route("/json/guardar")
@login_required
def guardar_json():
    nombre   = (request.args.get("nombre") or "Producto JSON").strip()
    cantidad = _as_int(request.args.get("cantidad"), 1)
    precio   = _as_float(request.args.get("precio"), 1.0)
    fecha    = datetime.now().isoformat(timespec="seconds")
    data = _json_load()
    data.append({"fecha": fecha, "nombre": nombre, "cantidad": cantidad, "precio": precio})
    _json_save(data)
    return {"ok": True, "total_registros": len(data)}

@app.route("/json/ver")
@login_required
def ver_json():
    data = _json_load()
    return f"<pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre>"

CSV_PATH = DATOS_DIR / "datos.csv"

@app.route("/csv/guardar")
@login_required
def guardar_csv():
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
@login_required
def ver_csv():
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        return "<pre>(archivo vacío)</pre>"
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return f"<pre>{json.dumps(rows, ensure_ascii=False, indent=2)}</pre>"

# Importadores a SQLite
def _upsert_producto(nombre: str, cantidad: int, precio: float):
    if not nombre: return False
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM productos WHERE nombre=?", (nombre,)).fetchone()
        if row:
            conn.execute(
                "UPDATE productos SET cantidad = cantidad + ?, precio = ? WHERE id = ?",
                (max(0, cantidad), max(0.0, precio), row["id"])
            )
        else:
            conn.execute(
                "INSERT INTO productos(nombre, cantidad, precio) VALUES (?,?,?)",
                (nombre, max(0, cantidad), max(0.0, precio))
            )
        conn.commit()
    return True

@app.route("/import/txt")
@login_required
def import_txt():
    if not TXT_PATH.exists():
        return {"ok": False, "msg": "datos.txt no existe"}
    procesados = 0
    for line in TXT_PATH.read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 4: continue
        _, nombre, cant, prec = parts
        procesados += 1 if _upsert_producto(nombre, _as_int(cant, 0), _as_float(prec, 0.0)) else 0
    return {"ok": True, "origen": "txt", "procesados": procesados}

@app.route("/import/json")
@login_required
def import_json():
    if not JSON_PATH.exists():
        return {"ok": False, "msg": "datos.json no existe"}
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "msg": "JSON inválido"}
    procesados = 0
    for obj in data if isinstance(data, list) else []:
        nombre = (obj.get("nombre") or "").strip()
        procesados += 1 if _upsert_producto(nombre, _as_int(obj.get("cantidad"), 0),
                                            _as_float(obj.get("precio"), 0.0)) else 0
    return {"ok": True, "origen": "json", "procesados": procesados}

@app.route("/import/csv")
@login_required
def import_csv():
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        return {"ok": False, "msg": "datos.csv vacío o no existe"}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    procesados = 0
    for r in rows:
        nombre = (r.get("nombre") or "").strip()
        procesados += 1 if _upsert_producto(nombre, _as_int(r.get("cantidad"), 0),
                                            _as_float(r.get("precio"), 0.0)) else 0
    return {"ok": True, "origen": "csv", "procesados": procesados}

@app.route("/import/all")
@login_required
def import_all():
    res_txt  = import_txt()
    res_json = import_json()
    res_csv  = import_csv()
    def _c(r): return r.get("procesados", 0) if isinstance(r, dict) else 0
    c_txt, c_json, c_csv = _c(res_txt), _c(res_json), _c(res_csv)
    total = c_txt + c_json + c_csv
    try: flash(f"Importación: TXT={c_txt}, JSON={c_json}, CSV={c_csv} (Total={total})", "success")
    except Exception: pass
    return redirect(url_for("home"))

# ---------------------- Formularios (Flask-WTF) -----------------
class ProductoForm(FlaskForm):
    nombre   = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=50)])
    cantidad = IntegerField("Cantidad", validators=[DataRequired(), NumberRange(min=0)])
    precio   = DecimalField("Precio", places=2, validators=[DataRequired(), NumberRange(min=0)])
    enviar   = SubmitField("Guardar")

class DeleteForm(FlaskForm):
    enviar = SubmitField("Eliminar")

class UsuarioMySQLForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=100)])
    email  = StringField("Email",  validators=[DataRequired(), Email(), Length(max=120)])
    enviar = SubmitField("Agregar")

class RegisterForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=100)])
    email  = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=6, max=128)])
    enviar = SubmitField("Crear cuenta")

class LoginForm(FlaskForm):
    email  = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=6, max=128)])
    enviar = SubmitField("Iniciar sesión")

# ---------------------- Rutas productos (SQLite) ----------------
@app.route("/")
@login_required
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
@login_required
def nuevo():
    form = ProductoForm()
    if form.validate_on_submit():
        with get_conn() as conn:
            conn.execute("INSERT INTO productos(nombre,cantidad,precio) VALUES (?,?,?)",
                         (form.nombre.data.strip(),
                          int(form.cantidad.data),
                          float(form.precio.data)))
            conn.commit()
        flash("Producto creado.", "success")
        return redirect(url_for("home"))
    return render_template("product_form.html", form=form, titulo="Nuevo producto")

@app.route("/editar/<int:pid>/", methods=["GET","POST"])
@login_required
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
                         (form.nombre.data.strip(),
                          int(form.cantidad.data),
                          float(form.precio.data),
                          pid))
            conn.commit()
        flash("Producto actualizado.", "success")
        return redirect(url_for("home"))
    return render_template("product_form.html", form=form, titulo=f"Editar (ID {pid})")

@app.route("/eliminar/<int:pid>/", methods=["POST"])
@login_required
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
@login_required
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

# ---------------------- SQLAlchemy (demo usuarios.db) -----------
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
@login_required
def usuarios_crear():
    nombre = (request.args.get("nombre") or "Usuario Demo").strip()
    email  = (request.args.get("email") or "demo@mail.com").strip()
    with Session() as s:
        s.add(Usuario(nombre=nombre, email=email))
        s.commit()
    return {"ok": True, "mensaje": f"Usuario '{nombre}' creado"}

@app.route("/usuarios/listar")
@login_required
def usuarios_listar():
    with Session() as s:
        users = s.query(Usuario).order_by(Usuario.id).all()
    data = [{"id": u.id, "nombre": u.nombre, "email": u.email} for u in users]
    return f"<pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre>"

# ---------------------- TEST MySQL ------------------------------
@app.route("/test_db")
def test_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = cur.fetchall()
    cur.close(); conn.close()
    return f"OK MySQL → {tables}"

# ---------------------- CRUD mínimo MySQL (tabla usuarios) ------
def mysql_fetch_all(sql, params=()):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

def mysql_fetch_one(sql, params=()):  # <-- (AÑADIDO) helper para 1 fila
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

def mysql_execute(sql, params=()):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    cur.close(); conn.close()

@app.route("/mysql/usuarios", methods=["GET", "POST"])
@login_required
def mysql_usuarios():
    form = UsuarioMySQLForm()
    if form.validate_on_submit():
        try:
            mysql_execute(
                "INSERT INTO usuarios (nombre, email, password_hash) VALUES (%s, %s, %s)",
                (form.nombre.data.strip(), form.email.data.strip(), "PLACEHOLDER")  # panel admin básico
            )
            flash("Usuario creado en MySQL (sin contraseña real).", "success")
            return redirect(url_for("mysql_usuarios"))
        except Exception as e:
            flash(f"Error al crear usuario: {e}", "danger")

    usuarios = mysql_fetch_all("SELECT id, nombre, email FROM usuarios ORDER BY id")
    return render_template("mysql_usuarios.html", usuarios=usuarios, form=form, titulo="Usuarios (MySQL)")

@app.route("/mysql/usuarios/eliminar/<int:uid>", methods=["POST"])
@login_required
def mysql_usuarios_eliminar(uid: int):
    try:
        mysql_execute("DELETE FROM usuarios WHERE id = %s", (uid,))
        flash(f"Usuario {uid} eliminado.", "info")
    except Exception as e:
        flash(f"Error eliminando usuario: {e}", "danger")
    return redirect(url_for("mysql_usuarios"))

# ---------------------- Productos (MySQL) paginado + CRUD -------
class ProductoMySQLForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=100)])
    precio = DecimalField("Precio", places=2, validators=[DataRequired(), NumberRange(min=0)])
    stock  = IntegerField("Stock", validators=[DataRequired(), NumberRange(min=0)])
    enviar = SubmitField("Guardar")

@app.route("/mysql/productos")
@login_required
def mysql_productos():
    page, per_page = get_page_args(default_per_page=8)
    total = mysql_scalar("SELECT COUNT(*) FROM productos")
    offset = (page - 1) * per_page
    # *** Cambio clave: mostrar los más nuevos primero (DESC) ***
    productos = mysql_fetch_all(
        "SELECT id_producto, nombre, precio, stock FROM productos ORDER BY id_producto DESC LIMIT %s OFFSET %s",
        (per_page, offset)
    )
    ctx = paginate_context(total, page, per_page, "mysql_productos")
    return render_template("mysql_productos.html", productos=productos, titulo="Productos (MySQL)", **ctx)

@app.route("/mysql/productos/crear", methods=["GET","POST"])
@login_required
def mysql_productos_crear():
    form = ProductoMySQLForm()
    if form.validate_on_submit():
        try:
            mysql_execute(
                "INSERT INTO productos (nombre, precio, stock) VALUES (%s, %s, %s)",
                (form.nombre.data.strip(), float(form.precio.data), int(form.stock.data))
            )
            flash("Producto creado.", "success")
            # Mostrará el nuevo en la parte superior (DESC)
            return redirect(url_for("mysql_productos"))
        except Exception as e:
            flash(f"Error creando producto: {e}", "danger")
    return render_template("mysql_producto_form.html", form=form, titulo="Nuevo producto (MySQL)")

@app.route("/mysql/productos/editar/<int:pid>", methods=["GET","POST"])
@login_required
def mysql_productos_editar(pid: int):
    row = mysql_fetch_all(
        "SELECT id_producto, nombre, precio, stock FROM productos WHERE id_producto=%s", (pid,)
    )
    if not row:
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("mysql_productos"))
    form = ProductoMySQLForm()
    if request.method == "GET":
        form.nombre.data = row[0]["nombre"]
        form.precio.data = row[0]["precio"]
        form.stock.data  = row[0]["stock"]
    if form.validate_on_submit():
        try:
            mysql_execute(
                "UPDATE productos SET nombre=%s, precio=%s, stock=%s WHERE id_producto=%s",
                (form.nombre.data.strip(), float(form.precio.data), int(form.stock.data), pid)
            )
            flash("Producto actualizado.", "success")
            return redirect(url_for("mysql_productos"))
        except Exception as e:
            flash(f"Error actualizando producto: {e}", "danger")
    return render_template("mysql_producto_form.html", form=form, titulo=f"Editar producto #{pid}")

@app.route("/mysql/productos/eliminar/<int:pid>", methods=["POST"])
@login_required
def mysql_productos_eliminar(pid: int):
    try:
        mysql_execute("DELETE FROM productos WHERE id_producto=%s", (pid,))
        flash("Producto eliminado.", "info")
    except Exception as e:
        flash(f"Error eliminando producto: {e}", "danger")
    return redirect(url_for("mysql_productos"))

# ---------------------- Categorías (MySQL) paginado + CRUD ------
@app.route("/mysql/categorias")
@login_required
def mysql_categorias():
    page, per_page = get_page_args(default_per_page=8)
    total = mysql_scalar("SELECT COUNT(*) FROM categorias")
    offset = (page - 1) * per_page
    categorias = mysql_fetch_all(
        "SELECT id_categoria, nombre FROM categorias ORDER BY id_categoria LIMIT %s OFFSET %s",
        (per_page, offset)
    )
    ctx = paginate_context(total, page, per_page, "mysql_categorias")
    return render_template("mysql_categorias.html", categorias=categorias, titulo="Categorías (MySQL)", **ctx)

@app.route("/mysql/categorias/crear", methods=["GET","POST"])
@login_required
def mysql_categorias_crear():
    form = CategoriaMySQLForm()
    if form.validate_on_submit():
        try:
            mysql_execute("INSERT INTO categorias (nombre) VALUES (%s)", (form.nombre.data.strip(),))
            flash("Categoría creada.", "success")
            return redirect(url_for("mysql_categorias"))
        except Exception as e:
            flash(f"Error creando categoría: {e}", "danger")
    return render_template("mysql_categoria_form.html", form=form, titulo="Nueva categoría")

@app.route("/mysql/categorias/editar/<int:cid>", methods=["GET","POST"])
@login_required
def mysql_categorias_editar(cid: int):
    row = mysql_fetch_all("SELECT id_categoria, nombre FROM categorias WHERE id_categoria=%s", (cid,))
    if not row:
        flash("Categoría no encontrada.", "warning")
        return redirect(url_for("mysql_categorias"))
    form = CategoriaMySQLForm()
    if request.method == "GET":
        form.nombre.data = row[0]["nombre"]
    if form.validate_on_submit():
        try:
            mysql_execute("UPDATE categorias SET nombre=%s WHERE id_categoria=%s",
                          (form.nombre.data.strip(), cid))
            flash("Categoría actualizada.", "success")
            return redirect(url_for("mysql_categorias"))
        except Exception as e:
            flash(f"Error actualizando categoría: {e}", "danger")
    return render_template("mysql_categoria_form.html", form=form, titulo=f"Editar categoría #{cid}")

@app.route("/mysql/categorias/eliminar/<int:cid>", methods=["POST"])
@login_required
def mysql_categorias_eliminar(cid: int):
    try:
        mysql_execute("DELETE FROM categorias WHERE id_categoria=%s", (cid,))
        flash("Categoría eliminada.", "info")
    except Exception as e:
        flash(f"Error eliminando categoría: {e}", "danger")
    return redirect(url_for("mysql_categorias"))

# ---------------------- AUTH (Flask-Login + MySQL) --------------
@app.route("/auth/register", methods=["GET", "POST"])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for("panel"))
    form = RegisterForm()
    if form.validate_on_submit():
        if get_user_by_email(form.email.data.strip()):
            flash("Ese email ya está registrado.", "warning")
        else:
            create_user(form.nombre.data.strip(), form.email.data.strip(), form.password.data)
            flash("Cuenta creada. Ahora inicia sesión.", "success")
            return redirect(url_for("auth_login"))
    return render_template("auth_register.html", form=form, titulo="Crear cuenta")

@app.route("/auth/login", methods=["GET", "POST"])
def auth_login():
    if current_user.is_authenticated:
        return redirect(url_for("panel"))
    form = LoginForm()
    if form.validate_on_submit():
        row = get_user_by_email(form.email.data.strip())
        if not row or not row.get("password_hash") or not check_password_hash(row["password_hash"], form.password.data):
            flash("Credenciales inválidas.", "danger")
        else:
            user = User(row["id"], row["nombre"], row["email"])
            login_user(user, remember=True)
            flash(f"Bienvenido, {user.nombre}.", "success")
            next_url = request.args.get("next") or url_for("panel")
            return redirect(next_url)
    return render_template("auth_login.html", form=form, titulo="Iniciar sesión")

@app.route("/auth/logout")
@login_required
def auth_logout():
    nombre = current_user.nombre
    logout_user()
    flash(f"Hasta luego, {nombre}.", "info")
    return redirect(url_for("auth_login"))

@app.route("/panel")
@login_required
def panel():
    return render_template("panel.html", titulo="Panel")

# ---------------------- CRUD MySQL: productos (AÑADIDO) ---------
class ProductoMySQLForm(FlaskForm):  # formulario para MySQL
    nombre = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=100)])
    precio = DecimalField("Precio", places=2, validators=[DataRequired(), NumberRange(min=0)])
    stock  = IntegerField("Stock", validators=[DataRequired(), NumberRange(min=0)])
    enviar = SubmitField("Guardar")

@app.route("/mysql/productos")
@login_required
def mysql_productos_list():
    filas = mysql_fetch_all(
        "SELECT id_producto, nombre, precio, stock FROM productos ORDER BY id_producto"
    )
    return render_template("mysql_productos.html", productos=filas, titulo="Productos (MySQL)")

@app.route("/mysql/productos/crear", methods=["GET", "POST"])
@login_required
def mysql_productos_crear():
    form = ProductoMySQLForm()
    if form.validate_on_submit():
        try:
            mysql_execute(
                "INSERT INTO productos (nombre, precio, stock) VALUES (%s, %s, %s)",
                (form.nombre.data.strip(), float(form.precio.data), int(form.stock.data))
            )
            flash("Producto creado en MySQL.", "success")
            return redirect(url_for("mysql_productos_list"))
        except Exception as e:
            flash(f"Error al crear: {e}", "danger")
    return render_template("mysql_producto_form.html", form=form, titulo="Crear (MySQL)")

@app.route("/mysql/productos/editar/<int:id_producto>", methods=["GET", "POST"])
@login_required
def mysql_productos_editar(id_producto: int):
    row = mysql_fetch_one(
        "SELECT id_producto, nombre, precio, stock FROM productos WHERE id_producto=%s",
        (id_producto,)
    )
    if not row:
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("mysql_productos_list"))
    form = ProductoMySQLForm()
    if request.method == "GET":
        form.nombre.data = row["nombre"]
        form.precio.data = row["precio"]
        form.stock.data  = row["stock"]
    if form.validate_on_submit():
        try:
            mysql_execute(
                "UPDATE productos SET nombre=%s, precio=%s, stock=%s WHERE id_producto=%s",
                (form.nombre.data.strip(), float(form.precio.data), int(form.stock.data), id_producto)
            )
            flash("Producto actualizado.", "success")
            return redirect(url_for("mysql_productos_list"))
        except Exception as e:
            flash(f"Error al actualizar: {e}", "danger")
    return render_template("mysql_producto_form.html", form=form, titulo=f"Editar (ID {id_producto})")

@app.route("/mysql/productos/eliminar/<int:id_producto>", methods=["POST"])
@login_required
def mysql_productos_eliminar(id_producto: int):
    try:
        mysql_execute("DELETE FROM productos WHERE id_producto=%s", (id_producto,))
        flash("Producto eliminado.", "info")
    except Exception as e:
        flash(f"Error al eliminar: {e}", "danger")
    return redirect(url_for("mysql_productos_list"))

# ---------------------- Punto de entrada ------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
