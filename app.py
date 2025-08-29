from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3

app = Flask(__name__)
app.config["SECRET_KEY"] = "cambia_esta_clave_super_secreta"

DB_PATH = "inventario.db"

# ---- DB ----
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

# ---- Forms ----
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DecimalField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

class ProductoForm(FlaskForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=50)])
    cantidad = IntegerField("Cantidad", validators=[DataRequired(), NumberRange(min=0)])
    precio   = DecimalField("Precio", places=2, validators=[DataRequired(), NumberRange(min=0)])
    enviar   = SubmitField("Guardar")

class DeleteForm(FlaskForm):
    enviar = SubmitField("Eliminar")

# ---- Rutas ----
@app.route("/")
def home():
    with get_conn() as conn:
        filas = conn.execute("SELECT id,nombre,cantidad,precio FROM productos ORDER BY id").fetchall()
    total_items = sum(p["cantidad"] for p in filas)
    total_valor = sum(p["cantidad"] * p["precio"] for p in filas)
    return render_template("index.html",
                           productos=filas,
                           delete_form=DeleteForm(),
                           total_items=total_items,
                           total_valor=total_valor,
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
                           productos=resultados,
                           delete_form=DeleteForm(),
                           total_items=total_items,
                           total_valor=total_valor,
                           q=q, titulo="Inventario")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
