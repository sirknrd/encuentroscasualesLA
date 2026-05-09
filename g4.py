import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import sqlite3
import json
import smtplib
from email.message import EmailMessage
import os
import base64
import uuid
from dotenv import load_dotenv

# ===================== CONFIG =====================
load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

DB_NAME = "registros.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===================== BASE DE DATOS =====================
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id TEXT PRIMARY KEY,
                timestamp TEXT,
                nombre TEXT,
                edad INTEGER,
                genero TEXT,
                email TEXT,
                ciudad TEXT,
                educacion TEXT,
                estado_civil TEXT,
                fuma TEXT,
                hijos TEXT,
                disponibilidad TEXT,
                interes TEXT,
                idiomas TEXT,
                gustos TEXT,
                fotos TEXT,
                respuestas TEXT
            )
        ''')
        conn.commit()

init_db()

# ===================== PREGUNTAS =====================
questions = [
    "¿Cuál es tu comida favorita?",
    "¿Prefieres la playa o la montaña?",
    "¿Qué tipo de música te gusta escuchar?",
    "¿Tienes algún hobby o pasatiempo favorito?",
    "¿Cuál es tu color favorito?",
    "¿Qué es lo que más valoras en una amistad?",
    "¿Cuál ha sido un momento que te hizo sentir realmente orgulloso/a?",
    "Si pudieras cambiar algo pequeño en tu día a día, ¿qué sería?",
    "¿Qué sueño tienes que aún no has cumplido?",
    "¿Qué te hace reír siempre?"
]

# ===================== APP =====================
app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True)

server = app.server  # Importante para Render

# ===================== LAYOUT =====================
app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("MEETLA", className="text-center text-primary my-4"))),
    dbc.Row(dbc.Col(html.H4("Desliza menos, vive más — Encuentros reales", 
                            className="text-center mb-5"))),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Completa tu perfil", className="card-title mb-4"),

                    dbc.Row([
                        dbc.Col(dbc.Input(id="nombre", placeholder="Nombre completo", type="text"), md=6),
                        dbc.Col(dbc.Input(id="edad", placeholder="Edad (18+)", type="number", min=18), md=6),
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col(dbc.Input(id="email", placeholder="Correo electrónico", type="email"), md=6),
                        dbc.Col(dcc.Dropdown(id="genero", placeholder="Género",
                            options=[{"label": x, "value": x} for x in ["Femenino", "Masculino", "No binario", "Otro"]]), md=6),
                    ], className="mb-3"),

                    dbc.Input(id="ciudad", placeholder="Ciudad / Localidad", className="mb-3"),

                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="educacion", placeholder="Nivel educativo",
                            options=[{"label": x, "value": x} for x in ["Educación media", "Técnico", "Universitario", "Posgrado"]]), md=6),
                        dbc.Col(dcc.Dropdown(id="estado_civil", placeholder="Estado civil",
                            options=[{"label": x, "value": x} for x in ["Soltero/a", "En pareja", "Casado/a", "Divorciado/a"]]), md=6),
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="fuma", placeholder="¿Fumas?",
                            options=[{"label": x, "value": x} for x in ["No", "Ocasionalmente", "Frecuentemente"]]), md=6),
                        dbc.Col(dcc.Dropdown(id="hijos", placeholder="¿Tienes hijos?",
                            options=[{"label": x, "value": x} for x in ["Sí", "No"]]), md=6),
                    ], className="mb-3"),

                    dcc.Dropdown(id="disponibilidad", placeholder="Disponibilidad horaria",
                        options=[{"label": x, "value": x} for x in ["Mañana", "Tarde", "Noche", "Fin de semana"]], className="mb-3"),

                    dcc.Dropdown(id="interes", placeholder="Interés principal",
                        options=[{"label": x, "value": x} for x in ["Relación seria", "Conocer personas", "Algo casual"]], className="mb-3"),

                    dbc.Textarea(id="idiomas", placeholder="Idiomas que hablas", className="mb-3"),
                    dbc.Textarea(id="gustos", placeholder="Gustos e intereses", className="mb-3"),

                    html.H5("Fotos (máximo 3)", className="mt-4"),
                    dcc.Upload(id='upload-photo', multiple=True, 
                        children=html.Div(['Arrastra o haz clic para seleccionar']),
                        className="border border-2 border-dashed p-4 text-center mb-3"),

                    html.Div(id="preview", className="d-flex flex-wrap gap-2 mb-4"),

                    html.H5("Preguntas para conocerte mejor", className="mt-4 text-center"),
                    html.Div([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label(q, className="fw-bold"),
                                dbc.Input(id=f"q{i}", type="text", placeholder="Tu respuesta...")
                            ], width=10, className="offset-md-1 mb-3")
                        ]) for i, q in enumerate(questions)
                    ]),

                    dbc.Button("Enviar Registro", id="submit-btn", color="success", size="lg", className="w-100 mt-4")
                ])
            ])
        ], md=10, lg=8)
    ], justify="center"),

    html.Div(id="mensaje", className="mt-4")
], fluid=True, className="py-4")

# ===================== CALLBACKS =====================
@app.callback(
    Output("preview", "children"),
    Input("upload-photo", "contents"),
    prevent_initial_call=True
)
def update_preview(contents):
    if not contents:
        return []
    return [html.Img(src=c, style={"height": "110px", "borderRadius": "8px", "margin": "5px"}) for c in contents[:3]]

@app.callback(
    Output("mensaje", "children"),
    Input("submit-btn", "n_clicks"),
    [State(f"q{i}", "value") for i in range(len(questions))] +
    [State("nombre", "value"), State("edad", "value"), State("email", "value"),
     State("genero", "value"), State("ciudad", "value"), State("educacion", "value"),
     State("estado_civil", "value"), State("fuma", "value"), State("hijos", "value"),
     State("disponibilidad", "value"), State("interes", "value"), State("idiomas", "value"),
     State("gustos", "value"), State("upload-photo", "contents")],
    prevent_initial_call=True
)
def submit_registration(*args):
    n_clicks = args[0]
    respuestas = args[1:11]
    datos_basicos = args[11:24]  # nombre hasta gustos
    contents = args[-1]

    if not all([datos_basicos[0], datos_basicos[1], datos_basicos[2]]):  # nombre, edad, email
        return dbc.Alert("Nombre, edad y correo son obligatorios", color="danger")

    record_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    photo_paths = []

    # Guardar fotos
    if contents:
        for content in contents[:3]:
            try:
                header, data = content.split(',')
                decoded = base64.b64decode(data)
                ext = "jpg" if "jpeg" in header else header.split('/')[1].split(';')[0]
                new_name = f"{record_id[:8]}_{uuid.uuid4().hex[:6]}.{ext}"
                path = os.path.join(UPLOAD_FOLDER, new_name)
                with open(path, "wb") as f:
                    f.write(decoded)
                photo_paths.append(new_name)
            except:
                continue

    # Guardar en DB
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO registros VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (record_id, timestamp, *datos_basicos, json.dumps(photo_paths), json.dumps(respuestas)))
            conn.commit()
    except Exception as e:
        return dbc.Alert(f"Error al guardar: {str(e)}", color="danger")

    # Enviar correo
    if EMAIL_ADDRESS and EMAIL_PASSWORD:
        try:
            msg = EmailMessage()
            msg['Subject'] = '✅ Registro exitoso - MEETLA'
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = datos_basicos[2]  # email
            msg.set_content(f"Hola {datos_basicos[0]},\n\n¡Gracias por registrarte en MEETLA!")
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)
        except:
            pass  # No romper si falla el email

    return dbc.Alert("¡Registro guardado con éxito! 🎉 Revisa tu correo.", color="success")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8050))
    app.run_server(debug=False, host="0.0.0.0", port=port)
