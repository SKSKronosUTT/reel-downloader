from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import re
from urllib.parse import urlparse

app = Flask(__name__)

# Configuración para descargas
DOWNLOAD_PATH = os.path.join(os.path.expanduser('~'), 'Downloads')

def is_valid_facebook_url(url):
    """Verifica si la URL es de Facebook"""
    facebook_patterns = [
        r'facebook\.com/share/v/',
        r'facebook\.com/watch',
        r'facebook\.com/video',
        r'fb\.watch'
    ]
    return any(re.search(pattern, url) for pattern in facebook_patterns)

def download_reel(url):
    """Descarga el reel de Facebook"""
    try:
        # Configuración de yt-dlp
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': os.path.join(tempfile.gettempdir(), '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Verificar si el archivo existe
            if os.path.exists(filename):
                return filename
            else:
                # Buscar el archivo si el nombre no coincide exactamente
                temp_dir = tempfile.gettempdir()
                files = [f for f in os.listdir(temp_dir) if f.endswith('.mp4')]
                if files:
                    # Tomar el archivo más reciente
                    latest_file = max([os.path.join(temp_dir, f) for f in files], key=os.path.getctime)
                    return latest_file
                return None
                
    except Exception as e:
        print(f"Error en download_reel: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'success': False, 'error': 'URL no proporcionada'}), 400
        
        if not is_valid_facebook_url(url):
            return jsonify({'success': False, 'error': 'URL de Facebook no válida'}), 400
        
        # Descargar el video
        video_path = download_reel(url)
        
        if not video_path or not os.path.exists(video_path):
            return jsonify({'success': False, 'error': 'No se pudo descargar el video'}), 500
        
        try:
            # Guardar en la carpeta de descargas
            filename = os.path.basename(video_path)
            download_path = os.path.join(DOWNLOAD_PATH, filename)
            
            # Si ya existe un archivo con el mismo nombre, agregar un número
            counter = 1
            base, ext = os.path.splitext(download_path)
            while os.path.exists(download_path):
                download_path = f"{base}_{counter}{ext}"
                counter += 1
            
            # Mover el archivo a la carpeta de descargas
            import shutil
            shutil.move(video_path, download_path)
            
            return jsonify({
                'success': True,
                'message': 'Descarga exitosa',
                'filename': os.path.basename(download_path)
            })
            
        except Exception as e:
            print(f"Error al mover archivo: {str(e)}")
            # Si falla, servir el archivo temporal
            return send_file(
                video_path,
                as_attachment=True,
                download_name=os.path.basename(video_path)
            )
            
    except Exception as e:
        print(f"Error general: {str(e)}")
        return jsonify({'success': False, 'error': f'Error al procesar la solicitud: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)