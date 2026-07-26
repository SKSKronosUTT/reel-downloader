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
import re
import time
from typing import Optional

import requests
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

app = Flask(__name__)

# Encabezados que imitan un navegador de escritorio normal. Facebook sirve
# una versión de la página con el video incrustado en JSON para este tipo
# de peticiones, sin necesidad de iniciar sesión (solo funciona con
# videos/Reels públicos).
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

# Facebook incrusta la URL del video en el HTML como un valor JSON escapado,
# bajo alguno de estos dos nombres de campo.
HD_PATTERN = re.compile(r'"playable_url_quality_hd":"([^"]+)"')
SD_PATTERN = re.compile(r'"playable_url":"([^"]+)"')

CHUNK_SIZE = 64 * 1024  # 64 KB por fragmento al retransmitir el video


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


def extract_video_url(facebook_url: str) -> Optional[str]:
    response = requests.get(facebook_url, headers=REQUEST_HEADERS, timeout=15)
    response.raise_for_status()
    html = response.text

    hd_match = HD_PATTERN.search(html)
    sd_match = SD_PATTERN.search(html)
    raw_url = hd_match.group(1) if hd_match else (sd_match.group(1) if sd_match else None)

    if not raw_url:
        return None
    return unescape_facebook_string(raw_url)


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
    except requests.RequestException:
        return jsonify({"error": "No se pudo conectar con Facebook. Intenta de nuevo."}), 502

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
            video_url, headers=REQUEST_HEADERS, stream=True, timeout=30
        )
        video_response.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "No se pudo descargar el video. Intenta de nuevo."}), 502

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
