# Descargar Reels de Facebook (Flask)

Aplicación web sencilla: pegas el link de un Reel de Facebook, tocas
**Descargar** y el video se guarda automáticamente en la carpeta de
Descargas del dispositivo desde el que abras la página (celular o
computadora). No usa base de datos ni guarda nada en el servidor.

## ⚠️ Aviso importante

La app obtiene el video leyendo el HTML público de la página de Facebook,
ya que no existe una API oficial de descarga para apps de terceros. Esto
significa:

- Solo funciona con Reels/videos **públicos** (la app no inicia sesión en
  Facebook).
- Si en algún momento Facebook cambia el formato interno de su página, la
  extracción puede dejar de funcionar hasta ajustar dos líneas de código
  (ver sección "Si deja de funcionar" más abajo).
- **Verifiqué que `facebook.com` y `fbcdn.net` están permitidos en el
  acceso a internet de las cuentas gratuitas de PythonAnywhere**, así que
  no necesitas una cuenta de pago para este proyecto. Si eso cambiara en
  el futuro, PythonAnywhere lo indicaría en pythonanywhere.com/whitelist.

## Cómo funciona

1. `templates/index.html` + `static/` → la página con la caja de texto,
   el botón "Pegar" (usa el portapapeles del navegador) y el botón
   "Descargar".
2. Al tocar "Descargar", el navegador manda el link a `POST /api/download`.
3. `app.py` descarga el HTML de esa página de Facebook, extrae la URL
   directa del .mp4 (HD si existe, si no SD) y la retransmite al
   navegador como un archivo adjunto — el propio navegador la guarda en
   Descargas.
4. Cuando la descarga del blob termina en el navegador, la página muestra
   la pantalla de "✅ Descargado con éxito" con un botón para volver.

## Estructura del proyecto

```
fb-reel-downloader/
├── app.py                  # Backend Flask (extracción + streaming del video)
├── requirements.txt
├── .gitignore
├── templates/
│   └── index.html
└── static/
    ├── css/style.css       # Paleta digital-blue
    └── js/main.js          # Lógica de pegar / descargar / mostrar éxito
```

## 1. Probarlo en tu computadora (opcional)

```bash
python -m venv venv
source venv/bin/activate      # En Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000` en el navegador.

## 2. Subirlo a GitHub

```bash
cd fb-reel-downloader
git init
git add .
git commit -m "Primera versión: descargador de Reels de Facebook"
```

Luego, en GitHub, crea un repositorio nuevo (vacío, sin README) y conecta
tu carpeta local con él:

```bash
git remote add origin https://github.com/TU-USUARIO/fb-reel-downloader.git
git branch -M main
git push -u origin main
```

## 3. Desplegarlo en PythonAnywhere

### a) Clonarlo desde la consola de PythonAnywhere
- Entra a tu cuenta → pestaña **Consoles** → **Bash**.
- Clona tu repositorio:

  ```bash
  git clone https://github.com/TU-USUARIO/fb-reel-downloader.git
  ```

### b) Crear el entorno virtual e instalar dependencias

```bash
cd fb-reel-downloader
mkvirtualenv --python=/usr/bin/python3.11 fb-reel-venv
pip install -r requirements.txt
```

(`mkvirtualenv` ya activa el entorno automáticamente. Si abres otra
consola más adelante, actívalo con `workon fb-reel-venv`.)

### c) Crear la web app
- Ve a la pestaña **Web** → **Add a new web app**.
- Elige **Manual configuration** (no "Flask", para poder usar tu propio
  `app.py` tal cual) y selecciona la misma versión de Python que usaste
  arriba (3.11).

### d) Configurar el virtualenv
- En la sección **Virtualenv** de la página de tu web app, escribe el
  nombre `fb-reel-venv` y presiona Enter. Debería mostrarte la ruta
  completa (`/home/TU-USUARIO/.virtualenvs/fb-reel-venv`).

### e) Editar el archivo WSGI
- En la sección **Code**, haz clic en el link del archivo WSGI (algo como
  `/var/www/tu_usuario_pythonanywhere_com_wsgi.py`).
- Borra el contenido de ejemplo y reemplázalo por:

  ```python
  import sys

  project_home = '/home/TU-USUARIO/fb-reel-downloader'
  if project_home not in sys.path:
      sys.path.insert(0, project_home)

  from app import app as application
  ```

  (Cambia `TU-USUARIO` por tu nombre de usuario real de PythonAnywhere.)

### f) Recargar
- Vuelve a la pestaña **Web** y presiona el botón verde **Reload**.
- Abre `https://TU-USUARIO.pythonanywhere.com` — ahí debería estar tu app.

### Para actualizar la app más adelante
Cada vez que hagas cambios y los subas a GitHub, en la consola Bash de
PythonAnywhere:

```bash
cd fb-reel-downloader
git pull
```

Y presiona **Reload** en la pestaña Web.

## Si deja de funcionar

Lo más probable es que Facebook haya cambiado el nombre de los campos en
su HTML. Abre `app.py` y ajusta estas dos líneas (se puede investigar el
nuevo patrón inspeccionando el código fuente de una página de video de
Facebook desde una computadora):

```python
HD_PATTERN = re.compile(r'"playable_url_quality_hd":"([^"]+)"')
SD_PATTERN = re.compile(r'"playable_url":"([^"]+)"')
```
