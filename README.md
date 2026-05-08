# MEETLA — Encuentros Reales en LATAM

**Desliza menos, vive más.**

Aplicación web para organizar encuentros casuales/reales en persona (citas en restaurantes, cafés, etc.) en Latinoamérica.

## Características

- Formulario completo de registro
- Subida de hasta 3 fotos
- Guardado en base de datos SQLite
- Envío de correo de confirmación
- Preparada para desplegar en **Render**

## Cómo ejecutar localmente

```bash
# 1. Clonar el repo
git clone https://github.com/sirknrd/encuentroscasualesLA.git
cd encuentroscasualesLA

# 2. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate    # En Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear archivo .env con tus credenciales
# (ver ejemplo abajo)

# 5. Ejecutar
python g4.py
