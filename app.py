from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "¡App Flask funcionando! Visita /usuario/Ariel"

@app.route("/usuario/<nombre>")
def usuario(nombre):
    return f"Bienvenido, {nombre}!"

if __name__ == "__main__":
    app.run(debug=True)
