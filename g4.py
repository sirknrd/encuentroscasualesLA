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
from datetime import datetime
from dotenv import load_dotenv

# ===================== CONFIG =====================
load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
    print("⚠️ Advertencia: Credenciales de email no configuradas")

DB_NAME = "registros.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===================== BASE DE DATOS =====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
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
    conn.close()

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
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                suppress_callback_exceptions=True)

server = app.server

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

                    # Datos básicos
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

                    # Más campos
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

                    dbc.Textarea(id="idiomas", placeholder="Idiomas que hablas (ej: Español, Inglés...)", className="mb-3"),
                    dbc.Textarea(id="gustos", placeholder="Gustos e intereses (música, cine, deportes, etc)", className="mb-3"),

                    # Fotos
                    html.H5("Fotos (máximo 3)", className="mt-4"),
                    dcc.Upload(id='upload-photo', multiple=True, 
                        children=html.Div(['Arrastra las fotos o haz clic para seleccionar']),
                        className="border border-2 border-dashed p-4 text-center mb-3"),

                    html.Div(id="preview", className="d-flex flex-wrap gap-2 mb-4"),

                    # Preguntas personales
                    html.H5("Preguntas para conocerte mejor", className="mt-4 text-center"),
                    html.Div(id="questions-container", children=[
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
    State("upload-photo", "filename"),
    prevent_initial_call=True
)
def update_preview(contents, filenames):
    if not contents:
        return []
    previews = []
    for c in contents[:3]:
        previews.append(html.Img(src=c, style={"height": "110px", "borderRadius": "8px", "margin": "5px"}))
    return previews


@app.callback(
    Output("mensaje", "children"),
    Input("submit-btn", "n_clicks"),
    [State(f"q{i}", "value") for i in range(len(questions))] +
    [State("nombre", "value"), State("edad", "value"), State("email", "value"),
     State("genero", "value"), State("ciudad", "value"), State("educacion", "value"),
     State("estado_civil", "value"), State("fuma", "value"), State("hijos", "value"),
     State("disponibilidad", "value"), State("interes", "value"), State("idiomas", "value"),
     State("gustos", "value"), State("upload-photo", "contents"), State("upload-photo", "filename")],
    prevent_initial_call=True
)
def submit_registration(*args):
    n_clicks = args[0]
    respuestas = args[1:11]          # Las 10 preguntas
    datos = args[11:-2]              # Datos básicos
    contents = args[-2]
    filenames = args[-1]

    if not datos[0] or not datos[1] or not datos[2]:  # nombre, edad, email
        return dbc.Alert("Nombre, edad y correo son obligatorios", color="danger")

    record_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    photo_paths = []

    # Guardar fotos
    if contents:
        for content, fname in zip(contents[:3], filenames[:3]):
            try:
                header, data = content.split(',')
                decoded = base64.b64decode(data)
                ext = fname.split('.')[-1]
                new_name = f"{record_id[:8]}_{uuid.uuid4().hex[:6]}.{ext}"
                path = os.path.join(UPLOAD_FOLDER, new_name)
                with open(path, "wb") as f:
                    f.write(decoded)
                photo_paths.append(new_name)
            except:
                continue

    # Guardar en DB
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO registros VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (record_id, timestamp, *datos, json.dumps(photo_paths), json.dumps(respuestas)))
    conn.commit()
    conn.close()

    return dbc.Alert("¡Registro guardado con éxito! 🎉", color="success")


if __name__ == '__main__':
    app.run_server(debug=True)
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
