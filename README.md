# MEETLA — Encuentros Reales en LATAM

**Desliza menos, vive más.**

Aplicación web para organizar encuentros casuales/reales en persona en Latinoamérica.
Formulario de registro con fotos, guardado en SQLite y correo de confirmación.

---

## Stack

- **Python 3.11+** · Dash · Dash Bootstrap Components
- **SQLite** (local) — reemplazable por PostgreSQL en producción
- **Gunicorn** para deploy en Render
- Correo vía **Gmail SMTP SSL**

---

## Ejecutar localmente

```bash
# 1. Clonar
git clone https://github.com/sirknrd/encuentroscasualesLA.git
cd encuentroscasualesLA

# 2. Entorno virtual
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Dependencias
pip install -r requirements.txt

# 4. Variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 5. Ejecutar
python app.py
```

Abre http://localhost:8050

---

## Variables de entorno

Crea un archivo `.env` (nunca lo commitees):

```
EMAIL_ADDRESS=tu_cuenta@gmail.com
EMAIL_PASSWORD=tu_app_password_de_gmail
UPLOAD_FOLDER=/tmp/meetla_uploads   # opcional, default: /tmp/meetla_uploads
```

> Para Gmail necesitas una **App Password** (no tu contraseña normal).
> Actívala en: Cuenta Google → Seguridad → Verificación en 2 pasos → Contraseñas de aplicación.

---

## Deploy en Render

1. Crear un **Web Service** apuntando a este repo.
2. Render detecta automáticamente el `Procfile`:
   ```
   web: gunicorn app:server
   ```
3. Agregar las variables de entorno `EMAIL_ADDRESS` y `EMAIL_PASSWORD` en el panel de Render.
4. **Importante:** El disco de Render es efímero — las fotos subidas se pierden al reiniciar.
   Para producción real, usa almacenamiento externo:
   - [Cloudinary](https://cloudinary.com/) (recomendado, tiene capa gratuita)
   - AWS S3 / Backblaze B2

---

## Limpieza del repositorio (hacer una sola vez)

El repo original tenía `.DS_Store` y `registros.db` commiteados. Para limpiarlos:

```bash
git rm --cached .DS_Store "registrations.json " registros.db
git commit -m "chore: remove tracked files that should be gitignored"
git push
```

---

## Estructura del proyecto

```
meetla/
├── app.py              # Aplicación principal (antes g4.py)
├── crear_datos.py      # Script de datos de ejemplo
├── requirements.txt    # Dependencias con versiones fijadas
├── Procfile            # Entry point para Render/Gunicorn
├── .gitignore
└── .env.example
```
