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

# Configura tu correo (usa variables de entorno reales en producción)
EMAIL_ADDRESS = "conradvonstillfried@gmail.com"
EMAIL_PASSWORD = "ivoz zlhw cczz rdxp"

DB_NAME = "registros.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

<p align="center">
  <img src="assets/logo.png" alt="MEETLA Logo" width="200"/>
</p>

<h1 align="center">MEETLA — Desliza menos, vive más</h1>
<p align="center">
  App de encuentros reales en restaurantes 🍷✨
</p>


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT,
                edad INTEGER,
                genero TEXT,
                localidad TEXT,
                email TEXT,
                educacion TEXT,
                estado_civil TEXT,
                fuma TEXT,
                hijos TEXT,
                disponibilidad TEXT,
                interes_romantico TEXT,
                idiomas TEXT,
                gustos TEXT,
                fotos TEXT,
                respuestas TEXT
            )
        ''')

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # necesario para Render

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.Img(src="/assets/logo.png", style={
            "height": "120px", "display": "block", "margin": "0 auto", "marginTop": "10px"
        }))
    ]),
    dbc.Row([
        dbc.Col(html.H2("MEETLA — Desliza menos, vive más",
                        className="text-center mb-4",
                        style={"color": "#d100c9", "fontWeight": "bold"}))
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Form([
                dbc.Row([
                    dbc.Col(dbc.Input(id="name", placeholder="Nombre", type="text"), md=6),
                    dbc.Col(dbc.Input(id="age", placeholder="Edad", type="number", min=18, max=99), md=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col(dbc.Input(id="email", placeholder="Correo electrónico", type="email"), md=6),
                    dbc.Col(dcc.Dropdown(
                        id="gender",
                        options=[
                            {"label": "Femenino", "value": "F"},
                            {"label": "Masculino", "value": "M"},
                            {"label": "Otro", "value": "O"},
                        ],
                        placeholder="Género"
                    ), md=6),
                ], className="mb-3"),
                dbc.Input(id="location", placeholder="Localidad", type="text", className="mb-3"),
                dcc.Dropdown(
                    id="educacion",
                    options=[{"label": l, "value": l} for l in ["Educación media", "Técnico profesional", "Universitario", "Postgrado"]],
                    placeholder="Nivel educacional",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="estado_civil",
                    options=[{"label": l, "value": l} for l in ["Soltero/a", "Separado/a", "Viudo/a"]],
                    placeholder="Estado civil",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="fuma",
                    options=[{"label": l, "value": l} for l in ["No", "Ocasionalmente", "Frecuentemente"]],
                    placeholder="¿Fumas?",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="hijos",
                    options=[{"label": l, "value": l} for l in ["Sí", "No"]],
                    placeholder="¿Tienes hijos?",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="disponibilidad",
                    options=[{"label": l, "value": l} for l in ["Mañana", "Tarde", "Noche"]],
                    placeholder="Disponibilidad horaria",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="interes",
                    options=[{"label": l, "value": l} for l in ["Relación seria", "Conocer personas", "Algo casual"]],
                    placeholder="Interés romántico",
                    className="mb-3"
                ),
                dbc.Textarea(id="idiomas", placeholder="Idiomas que hablas", className="mb-3"),
                dbc.Textarea(id="likes", placeholder="Gustos e intereses (cine, deportes, música, etc)", className="mb-3"),
                html.H5("Fotos (1 a 3):", className="mt-3"),
                dcc.Upload(id="upload-photo", multiple=True, children=html.Div([
                    'Arrastra tus fotos o haz click para subir (3 max)' ]),
                    style={
                        'width': '100%', 'height': '60px', 'lineHeight': '60px',
                        'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px',
                        'textAlign': 'center', 'marginBottom': '20px'
                    },
                    accept="image/*"
                ),
                html.Div(id="preview"),
                html.H5("Preguntas para conocerte mejor", className="mb-3 mt-4 text-center"),
                *generate_questions(),
                dbc.Button("Enviar", id="submit", color="primary", className="mt-3"),
                html.Div(id="mensaje", className="mt-3")
            ])
        ], md=8, className="offset-md-2")
    ])
], fluid=True)


def guardar_en_db(**datos):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO registros (
                nombre, edad, genero, localidad, email, educacion, estado_civil,
                fuma, hijos, disponibilidad, interes_romantico, idiomas, gustos, fotos, respuestas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', tuple(datos.values()))
        conn.commit()

def enviar_confirmacion(nombre, correo):
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Confirmación de registro - Cita en Restaurante'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = correo
        msg.set_content(f"""
Hola {nombre},

¡Gracias por registrarte en el evento de citas reales en restaurante!
Muy pronto recibirás los detalles de tu mesa y el grupo que te hemos asignado según tus preferencias.

Nos alegra que seas parte de esta experiencia ✨

— Equipo Encuentro Real 💛
""")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Error al enviar email: {e}")

questions = [
    "¿Cuál es tu comida favorita?",
    "¿Prefieres la playa o la montaña?",
    "¿Qué tipo de música te gusta escuchar?",
    "¿Tienes algún hobby o pasatiempo?",
    "¿Cuál es tu color favorito?",
    "¿Qué es lo que más valoras en una amistad?",
    "¿Cuál ha sido un momento que te hizo sentir realmente orgulloso/a?",
    "Si pudieras cambiar algo pequeño en tu día a día, ¿qué sería?",
    "¿Qué sueño tienes que aún no has cumplido?",
    "¿Qué te hace reír siempre?"
]

def save_photos(files):
    filenames = []
    for file in files:
        if file:
            try:
                content_type, content_string = file.split(',')
                ext = content_type.split('/')[1].split(';')[0]
                fname = f"{uuid.uuid4()}.{ext}"
                filepath = os.path.join(UPLOAD_FOLDER, fname)
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(content_string))
                filenames.append(filepath)
            except Exception as e:
                print(f"Error al guardar foto: {e}")
    return filenames

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # ← necesario para Render

def generate_questions():
    return [
        dbc.Row([
            dbc.Col([
                dbc.Label(q, className="fw-bold"),
                dbc.Input(type="text", id=f"q{i}", placeholder="Tu respuesta"),
            ], width=8, className="offset-md-2 mb-3")
        ]) for i, q in enumerate(questions)
    ]

app.layout = dbc.Container([
    dbc.Row([dbc.Col(html.H2("Registro Cita en Restaurante", className="text-center mb-4 text-primary"))]),
    dbc.Row([
        dbc.Col([
            dbc.Form([
                dbc.Row([
                    dbc.Col(dbc.Input(id="name", placeholder="Nombre", type="text"), md=6),
                    dbc.Col(dbc.Input(id="age", placeholder="Edad", type="number", min=18, max=99), md=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col(dbc.Input(id="email", placeholder="Correo electrónico", type="email"), md=6),
                    dbc.Col(dcc.Dropdown(
                        id="gender",
                        options=[
                            {"label": "Femenino", "value": "F"},
                            {"label": "Masculino", "value": "M"},
                            {"label": "Otro", "value": "O"},
                        ],
                        placeholder="Género"
                    ), md=6),
                ], className="mb-3"),
                dbc.Input(id="location", placeholder="Localidad", type="text", className="mb-3"),
                dcc.Dropdown(
                    id="educacion",
                    options=[{"label": l, "value": l} for l in ["Educación media", "Técnico profesional", "Universitario", "Postgrado"]],
                    placeholder="Nivel educacional",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="estado_civil",
                    options=[{"label": l, "value": l} for l in ["Soltero/a", "Separado/a", "Viudo/a"]],
                    placeholder="Estado civil",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="fuma",
                    options=[{"label": l, "value": l} for l in ["No", "Ocasionalmente", "Frecuentemente"]],
                    placeholder="¿Fumas?",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="hijos",
                    options=[{"label": l, "value": l} for l in ["Sí", "No"]],
                    placeholder="¿Tienes hijos?",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="disponibilidad",
                    options=[{"label": l, "value": l} for l in ["Mañana", "Tarde", "Noche"]],
                    placeholder="Disponibilidad horaria",
                    className="mb-3"
                ),
                dcc.Dropdown(
                    id="interes",
                    options=[{"label": l, "value": l} for l in ["Relación seria", "Conocer personas", "Algo casual"]],
                    placeholder="Interés romántico",
                    className="mb-3"
                ),
                dbc.Textarea(id="idiomas", placeholder="Idiomas que hablas", className="mb-3"),
                dbc.Textarea(id="likes", placeholder="Gustos e intereses (cine, deportes, música, etc)", className="mb-3"),
                html.H5("Fotos (1 a 3):", className="mt-3"),
                dcc.Upload(id="upload-photo", multiple=True, children=html.Div([
                    'Arrastra tus fotos o haz click para subir (3 max)' ]),
                    style={
                        'width': '100%', 'height': '60px', 'lineHeight': '60px',
                        'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px',
                        'textAlign': 'center', 'marginBottom': '20px'
                    },
                    accept="image/*"
                ),
                html.Div(id="preview"),
                html.H5("Preguntas para conocerte mejor", className="mb-3 mt-4 text-center"),
                *generate_questions(),
                dbc.Button("Enviar", id="submit", color="primary", className="mt-3"),
                html.Div(id="mensaje", className="mt-3")
            ])
        ], md=8, className="offset-md-2")
    ])
], fluid=True)

@app.callback(
    Output("mensaje", "children"),
    Output("preview", "children"),
    Input("submit", "n_clicks"),
    State("name", "value"), State("age", "value"), State("email", "value"),
    State("gender", "value"), State("location", "value"), State("educacion", "value"),
    State("estado_civil", "value"), State("fuma", "value"), State("hijos", "value"),
    State("disponibilidad", "value"), State("interes", "value"), State("idiomas", "value"),
    State("likes", "value"), State("upload-photo", "contents"),
    *[State(f"q{i}", "value") for i in range(len(questions))],
    prevent_initial_call=True
)
def guardar(n, nombre, edad, email, genero, localidad, educacion, estado, fuma, hijos, disp, interes, idiomas, gustos, fotos, *respuestas):
    if not all([nombre, edad, email, genero, localidad]):
        return dbc.Alert("Por favor completa los campos obligatorios.", color="danger"), None
    if any(r is None or r.strip() == "" for r in respuestas):
        return dbc.Alert("Responde todas las preguntas.", color="danger"), None

    respuestas_dict = {questions[i]: respuestas[i] for i in range(len(questions))}
    fotos_guardadas = save_photos(fotos or [])[:3]
    datos = {
        "nombre": nombre, "edad": edad, "genero": genero, "localidad": localidad,
        "email": email, "educacion": educacion, "estado_civil": estado, "fuma": fuma,
        "hijos": hijos, "disponibilidad": disp, "interes_romantico": interes,
        "idiomas": idiomas, "gustos": json.dumps(gustos.split(",")),
        "fotos": json.dumps(fotos_guardadas), "respuestas": json.dumps(respuestas_dict)
    }
    guardar_en_db(**datos)
    enviar_confirmacion(nombre, email)
    previews = [html.Img(src=f"data:image/png;base64,{base64.b64encode(open(f, 'rb').read()).decode()}", style={"height": "100px", "marginRight": "10px"}) for f in fotos_guardadas]
    return dbc.Alert("Registro exitoso y correo enviado.\nGracias por participar!", color="success"), previews

if __name__ == "__main__":
    init_db()
    import os
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)
