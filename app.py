import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import json
import os
import base64
import uuid
from datetime import datetime
from dotenv import load_dotenv
import re
from collections import defaultdict
import time
import gspread
from google.oauth2.service_account import Credentials

# ===================== CONFIG =====================
load_dotenv()

SHEET_ID       = os.getenv("SHEET_ID", "180GCJ3KrtuvvY8I2aAKKJ3-5HBLCNEFfRy809xXk0Hk")
SHEET_NAME     = os.getenv("SHEET_NAME", "Hoja 1")
GOOGLE_CREDS   = os.getenv("GOOGLE_CREDS")  # JSON string con las credenciales

UPLOAD_FOLDER  = os.getenv("UPLOAD_FOLDER", "/tmp/meetla_uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

_submit_times: dict = defaultdict(list)
RATE_LIMIT_WINDOW = 300
RATE_LIMIT_MAX    = 3

# ===================== GOOGLE SHEETS =====================
def get_sheet():
    """Retorna la hoja de Google Sheets autenticada."""
    creds_dict = json.loads(GOOGLE_CREDS)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

def append_to_sheet(row: list) -> None:
    """Agrega una fila al Google Sheet."""
    sheet = get_sheet()
    sheet.append_row(row, value_input_option="USER_ENTERED")

# ===================== HELPERS =====================
def valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))

def sanitize_text(value, max_len: int = 500) -> str:
    if not value:
        return ""
    return str(value).strip()[:max_len]

def rate_limited(session_id: str) -> bool:
    now = time.time()
    _submit_times[session_id] = [t for t in _submit_times[session_id]
                                  if now - t < RATE_LIMIT_WINDOW]
    if len(_submit_times[session_id]) >= RATE_LIMIT_MAX:
        return True
    _submit_times[session_id].append(now)
    return False

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
    "¿Qué te hace reír siempre?",
]

# ===================== APP =====================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
server = app.server

# ===================== LAYOUT =====================
app.layout = dbc.Container([
    dcc.Store(id="session-id", storage_type="session", data=str(uuid.uuid4())),

    dbc.Row(dbc.Col(html.H1("MEETLA", className="text-center text-primary my-4"))),
    dbc.Row(dbc.Col(html.H4("Desliza menos, vive más — Encuentros reales",
                            className="text-center mb-5"))),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Completa tu perfil", className="card-title mb-4"),

                    dbc.Row([
                        dbc.Col(dbc.Input(id="nombre", placeholder="Nombre completo",
                                         type="text", maxLength=100), md=6),
                        dbc.Col(dbc.Input(id="edad", placeholder="Edad (18+)",
                                         type="number", min=18, max=120), md=6),
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col(dbc.Input(id="email", placeholder="Correo electrónico",
                                         type="email", maxLength=200), md=6),
                        dbc.Col(dcc.Dropdown(id="genero", placeholder="Género",
                            options=[{"label": x, "value": x}
                                     for x in ["Femenino", "Masculino",
                                               "No binario", "Otro"]]), md=6),
                    ], className="mb-3"),

                    dbc.Input(id="ciudad", placeholder="Ciudad / Localidad",
                              maxLength=100, className="mb-3"),

                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="educacion", placeholder="Nivel educativo",
                            options=[{"label": x, "value": x}
                                     for x in ["Educación media", "Técnico",
                                               "Universitario", "Posgrado"]]), md=6),
                        dbc.Col(dcc.Dropdown(id="estado_civil", placeholder="Estado civil",
                            options=[{"label": x, "value": x}
                                     for x in ["Soltero/a", "En pareja",
                                               "Casado/a", "Divorciado/a"]]), md=6),
                    ], className="mb-3"),

                    dbc.Row([
                        dbc.Col(dcc.Dropdown(id="fuma", placeholder="¿Fumas?",
                            options=[{"label": x, "value": x}
                                     for x in ["No", "Ocasionalmente",
                                               "Frecuentemente"]]), md=6),
                        dbc.Col(dcc.Dropdown(id="hijos", placeholder="¿Tienes hijos?",
                            options=[{"label": x, "value": x}
                                     for x in ["Sí", "No"]]), md=6),
                    ], className="mb-3"),

                    dcc.Dropdown(id="disponibilidad", placeholder="Disponibilidad horaria",
                        options=[{"label": x, "value": x}
                                 for x in ["Mañana", "Tarde", "Noche", "Fin de semana"]],
                        className="mb-3"),

                    dcc.Dropdown(id="interes", placeholder="Interés principal",
                        options=[{"label": x, "value": x}
                                 for x in ["Relación seria", "Conocer personas",
                                           "Algo casual"]],
                        className="mb-3"),

                    dbc.Textarea(id="idiomas", placeholder="Idiomas que hablas",
                                 maxLength=200, className="mb-3"),
                    dbc.Textarea(id="gustos", placeholder="Gustos e intereses",
                                 maxLength=500, className="mb-3"),

                    html.H5("Fotos (opcional, máximo 3)", className="mt-4"),
                    html.P("Formatos aceptados: JPG, PNG, GIF, WEBP",
                           className="text-muted small"),
                    dcc.Upload(
                        id="upload-photo", multiple=True, accept="image/*",
                        children=html.Div(["Arrastra o haz clic para seleccionar"]),
                        className="border border-2 border-dashed p-4 text-center mb-3",
                    ),
                    html.Div(id="preview", className="d-flex flex-wrap gap-2 mb-2"),
                    html.Div(id="foto-error", className="text-danger small mb-3"),

                    html.H5("Preguntas para conocerte mejor", className="mt-4 text-center"),
                    html.Div([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label(q, className="fw-bold"),
                                dbc.Input(id=f"q{i}", type="text",
                                          placeholder="Tu respuesta...", maxLength=300),
                            ], width=10, className="offset-md-1 mb-3")
                        ])
                        for i, q in enumerate(questions)
                    ]),

                    dbc.Button("Enviar Registro", id="submit-btn",
                               color="success", size="lg", className="w-100 mt-4"),
                ])
            ])
        ], md=10, lg=8)
    ], justify="center"),

    html.Div(id="mensaje", className="mt-4"),
], fluid=True, className="py-4")


# ===================== CALLBACKS =====================

@app.callback(
    Output("preview", "children"),
    Output("foto-error", "children"),
    Input("upload-photo", "contents"),
    Input("upload-photo", "filename"),
    prevent_initial_call=True,
)
def update_preview(contents, filenames):
    if not contents:
        return [], ""
    previews, errors = [], []
    for content, fname in zip(contents[:3], (filenames or [])[:3]):
        header = content.split(",")[0]
        mime = header.replace("data:", "").replace(";base64", "").lower()
        if mime not in ALLOWED_MIME_TYPES:
            errors.append(f"'{fname}' no es una imagen válida.")
            continue
        previews.append(html.Img(src=content,
                                 style={"height": "110px", "borderRadius": "8px",
                                        "margin": "5px"}))
    return previews, "  ".join(errors)


@app.callback(
    Output("mensaje", "children"),
    Input("submit-btn", "n_clicks"),
    [State(f"q{i}", "value") for i in range(len(questions))]
    + [
        State("nombre",         "value"),
        State("edad",           "value"),
        State("email",          "value"),
        State("genero",         "value"),
        State("ciudad",         "value"),
        State("educacion",      "value"),
        State("estado_civil",   "value"),
        State("fuma",           "value"),
        State("hijos",          "value"),
        State("disponibilidad", "value"),
        State("interes",        "value"),
        State("idiomas",        "value"),
        State("gustos",         "value"),
        State("upload-photo",   "contents"),
        State("upload-photo",   "filename"),
        State("session-id",     "data"),
    ],
    prevent_initial_call=True,
)
def submit_registration(*args):
    respuestas = list(args[1:11])
    (nombre, edad, email, genero, ciudad, educacion,
     estado_civil, fuma, hijos, disponibilidad,
     interes, idiomas, gustos) = args[11:24]
    contents   = args[24]
    filenames  = args[25]
    session_id = args[26]

    # Validaciones
    if not nombre or not edad or not email:
        return dbc.Alert("Nombre, edad y correo son obligatorios.", color="danger")
    if not valid_email(email):
        return dbc.Alert("El correo no tiene un formato válido.", color="danger")
    try:
        edad_int = int(edad)
        if edad_int < 18:
            return dbc.Alert("Debes tener 18 años o más.", color="danger")
    except (TypeError, ValueError):
        return dbc.Alert("La edad debe ser un número.", color="danger")
    if rate_limited(session_id or "anon"):
        return dbc.Alert("Demasiados intentos. Espera unos minutos.", color="warning")

    # Sanitizar
    nombre    = sanitize_text(nombre, 100)
    ciudad    = sanitize_text(ciudad, 100)
    idiomas   = sanitize_text(idiomas, 200)
    gustos    = sanitize_text(gustos, 500)
    respuestas = [sanitize_text(r, 300) for r in respuestas]

    record_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Guardar fotos (opcional)
    photo_names: list[str] = []
    if contents:
        for content, fname in zip(contents[:3], (filenames or [None]*3)[:3]):
            try:
                header, data = content.split(",")
                mime = header.replace("data:", "").replace(";base64", "").lower()
                if mime not in ALLOWED_MIME_TYPES:
                    continue
                decoded = base64.b64decode(data)
                ext = mime.split("/")[1].split("+")[0]
                ext = "jpg" if ext == "jpeg" else ext
                new_name = f"{record_id[:8]}_{uuid.uuid4().hex[:6]}.{ext}"
                with open(os.path.join(UPLOAD_FOLDER, new_name), "wb") as f:
                    f.write(decoded)
                photo_names.append(new_name)
            except Exception:
                continue

    # Fila para Google Sheets — 26 columnas
    row = [
        record_id, timestamp,
        nombre, edad_int, genero or "", email,
        ciudad, educacion or "", estado_civil or "",
        fuma or "", hijos or "", disponibilidad or "", interes or "",
        idiomas, gustos,
        respuestas[0], respuestas[1], respuestas[2], respuestas[3],
        respuestas[4], respuestas[5], respuestas[6], respuestas[7],
        respuestas[8], respuestas[9],
        ", ".join(photo_names),  # fotos (opcional)
    ]

    try:
        append_to_sheet(row)
    except Exception as e:
        return dbc.Alert(f"Error al guardar en Google Sheets: {e}", color="danger")

    return dbc.Alert("¡Registro guardado con éxito! 🎉", color="success")


# ===================== ENTRY POINT =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)
