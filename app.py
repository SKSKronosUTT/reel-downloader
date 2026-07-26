"""
Descargar Reels de Facebook — app Flask

Flujo:
  1. El usuario pega el link del Reel en la página principal (templates/index.html).
  2. El navegador hace un POST a /api/download con { "url": "<link>" }.
  3. El servidor descarga el HTML público de esa página de Facebook y extrae
     la URL directa del archivo .mp4 (HD si está disponible, si no SD).
  4. El servidor descarga ese video y lo retransmite (stream) al navegador
     como un archivo adjunto, para que el propio navegador lo guarde en la
     carpeta de Descargas del usuario.

No se guarda nada en el servidor ni en una base de datos: todo ocurre en
memoria mientras se retransmite el archivo.
"""

import json
import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse, urlunparse

import requests
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Encabezados que imitan un navegador de escritorio normal lo más fielmente
# posible. Facebook es agresivo bloqueando peticiones que "huelen" a bot,
# así que entre más completo este set, mejor.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Facebook incrusta la URL del video en el HTML como un valor JSON escapado,
# bajo alguno de estos dos nombres de campo.
HD_PATTERN = re.compile(r'"playable_url_quality_hd":"([^"]+)"')
SD_PATTERN = re.compile(r'"playable_url":"([^"]+)"')

CHUNK_SIZE = 64 * 1024  # 64 KB por fragmento al retransmitir el video


class ExtractionError(Exception):
    """Error ya con un mensaje listo para mostrarle al usuario."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def is_facebook_link(url: str) -> bool:
    return "facebook.com" in url or "fb.watch" in url


def unescape_facebook_string(raw: str) -> str:
    """Facebook escapa la URL como si fuera un string JSON (ej. usa \\/
    en vez de /). Reutilizamos el parser JSON de la librería estándar
    para desescaparla de forma correcta y segura."""
    try:
        return json.loads(f'"{raw}"')
    except (ValueError, json.JSONDecodeError):
        return raw.replace("\\/", "/")


def find_video_url_in_html(html: str) -> Optional[str]:
    hd_match = HD_PATTERN.search(html)
    sd_match = SD_PATTERN.search(html)
    raw_url = hd_match.group(1) if hd_match else (sd_match.group(1) if sd_match else None)
    if not raw_url:
        return None
    return unescape_facebook_string(raw_url)


def to_mbasic_url(url: str) -> Optional[str]:
    """Convierte un link normal de facebook.com a su versión mbasic
    (pensada para navegadores simples), que a veces evita bloqueos que sí
    aplican a la versión de escritorio."""
    parsed = urlparse(url)
    if "facebook.com" not in parsed.netloc:
        return None
    return urlunparse(parsed._replace(netloc="mbasic.facebook.com", scheme="https"))


def fetch_page(session: requests.Session, url: str) -> str:
    try:
        response = session.get(url, timeout=15, allow_redirects=True)
    except requests.RequestException as exc:
        logger.exception("Fallo de red al pedir %s", url)
        raise ExtractionError(
            "No se pudo conectar con Facebook (fallo de red desde el servidor). "
            "Intenta de nuevo en unos minutos."
        ) from exc

    if response.status_code != 200:
        # Guardamos un fragmento de la respuesta en el log del servidor para
        # poder diagnosticar (en PythonAnywhere: pestaña Web -> Error log).
        logger.warning(
            "Facebook respondio %s para %s. Primeros 300 caracteres: %r",
            response.status_code,
            url,
            response.text[:300],
        )
        raise ExtractionError(
            f"Facebook respondió con un error (código {response.status_code}) al pedir "
            "esa página. Es probable que esté bloqueando temporalmente peticiones "
            "automáticas desde este servidor; intenta de nuevo más tarde."
        )

    return response.text


def extract_video_url(facebook_url: str) -> Optional[str]:
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    html = fetch_page(session, facebook_url)
    video_url = find_video_url_in_html(html)
    if video_url:
        return video_url

    # No se encontró en la versión normal: probamos con la versión mbasic,
    # que a veces sirve el HTML de forma más simple/directa.
    mbasic_url = to_mbasic_url(facebook_url)
    if mbasic_url and mbasic_url != facebook_url:
        try:
            html = fetch_page(session, mbasic_url)
            video_url = find_video_url_in_html(html)
        except ExtractionError:
            pass  # nos quedamos con "no encontrado" del intento original

    return video_url


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    facebook_url = (data.get("url") or "").strip()

    if not facebook_url:
        return jsonify({"error": "Pega el link del Reel primero."}), 400

    if not is_facebook_link(facebook_url):
        return jsonify({"error": "Ese no parece un link de Facebook."}), 400

    try:
        video_url = extract_video_url(facebook_url)
    except ExtractionError as exc:
        return jsonify({"error": exc.user_message}), 502

    if not video_url:
        return (
            jsonify(
                {
                    "error": "No se pudo encontrar el video en ese link. "
                    "Verifica que el Reel sea público y que el link sea correcto."
                }
            ),
            422,
        )

    try:
        video_response = requests.get(
            video_url, headers=BROWSER_HEADERS, stream=True, timeout=30
        )
        video_response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Fallo al descargar el video desde %s", video_url)
        status = getattr(exc.response, "status_code", None)
        detail = f" (código {status})" if status else ""
        return jsonify({"error": f"No se pudo descargar el video{detail}. Intenta de nuevo."}), 502

    filename = f"reel_{int(time.time())}.mp4"

    def generate():
        try:
            for chunk in video_response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    yield chunk
        finally:
            video_response.close()

    return Response(
        stream_with_context(generate()),
        mimetype="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    # Solo se usa para correrlo en tu computadora con `python app.py`.
    # En PythonAnywhere, el archivo WSGI importa directamente `app`.
    app.run(debug=True)
