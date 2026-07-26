from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import re
import shutil
import logging
from datetime import datetime

app = Flask(__name__)

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuración para descargas
DOWNLOAD_PATH = os.path.join(os.path.expanduser('~'), 'Downloads')

# Asegurar que la carpeta de descargas existe
if not os.path.exists(DOWNLOAD_PATH):
    try:
        os.makedirs(DOWNLOAD_PATH)
        logger.info(f"Carpeta de descargas creada en: {DOWNLOAD_PATH}")
    except Exception as e:
        logger.error(f"No se pudo crear la carpeta de descargas: {e}")

def is_valid_facebook_url(url):
    """Verifica si la URL es de Facebook"""
    facebook_patterns = [
        r'facebook\.com/share/v/',
        r'facebook\.com/watch',
        r'facebook\.com/video',
        r'facebook\.com/reel',
        r'fb\.watch',
        r'facebook\.com/.*?/videos/',
        r'facebook\.com/.*?/posts/'
    ]
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in facebook_patterns)

def clean_filename(filename):
    """Limpia el nombre del archivo para que sea válido en el sistema"""
    # Eliminar caracteres no válidos
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limitar longitud
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:195] + ext
    return filename

def download_reel(url):
    """Descarga el reel de Facebook con múltiples intentos y opciones"""
    temp_dir = tempfile.gettempdir()
    logger.info(f"Descargando desde: {url}")
    
    # Configuraciones alternativas para intentar
    configs = [
        {
            'format': 'best[ext=mp4]/best[ext=mov]/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        },
        {
            'format': 'best[height<=720]',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        }
    ]
    
    for idx, config in enumerate(configs, 1):
        try:
            logger.info(f"Intento {idx} con configuración: {config['format']}")
            
            with yt_dlp.YoutubeDL(config) as ydl:
                # Primero extraer información
                info = ydl.extract_info(url, download=False)
                if not info:
                    logger.error("No se pudo extraer información del video")
                    continue
                
                # Verificar si hay formato disponible
                if 'formats' in info and len(info['formats']) == 0:
                    logger.error("No hay formatos disponibles para este video")
                    continue
                
                # Descargar
                logger.info(f"Descargando: {info.get('title', 'Unknown')}")
                downloaded_file = ydl.download([url])
                
                # Buscar el archivo descargado
                temp_files = os.listdir(temp_dir)
                video_files = [f for f in temp_files if f.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))]
                
                if video_files:
                    # Ordenar por fecha de modificación (más reciente primero)
                    video_files.sort(key=lambda x: os.path.getmtime(os.path.join(temp_dir, x)), reverse=True)
                    latest_file = os.path.join(temp_dir, video_files[0])
                    
                    # Verificar que el archivo no esté vacío
                    if os.path.getsize(latest_file) > 1000:  # Mayor a 1KB
                        logger.info(f"Archivo descargado exitosamente: {latest_file}")
                        return latest_file
                    else:
                        logger.warning(f"Archivo demasiado pequeño: {latest_file}")
                        try:
                            os.remove(latest_file)
                        except:
                            pass
                
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Error de descarga en intento {idx}: {str(e)}")
            continue
        except Exception as e:
            logger.error(f"Error en intento {idx}: {str(e)}")
            continue
    
    # Si llegamos aquí, todos los intentos fallaron
    logger.error("Todos los intentos de descarga fallaron")
    return None

def find_video_in_temp():
    """Busca videos en el directorio temporal"""
    temp_dir = tempfile.gettempdir()
    video_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.3gp')
    
    try:
        files = os.listdir(temp_dir)
        video_files = [f for f in files if f.lower().endswith(video_extensions)]
        
        if video_files:
            # Ordenar por fecha de modificación
            video_files.sort(key=lambda x: os.path.getmtime(os.path.join(temp_dir, x)), reverse=True)
            return os.path.join(temp_dir, video_files[0])
    except Exception as e:
        logger.error(f"Error buscando videos en temp: {e}")
    
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json()
        if not data:
            logger.error("No se recibieron datos JSON")
            return jsonify({'success': False, 'error': 'No se recibieron datos'}), 400
            
        url = data.get('url', '').strip()
        logger.info(f"URL recibida: {url}")
        
        if not url:
            return jsonify({'success': False, 'error': 'URL no proporcionada'}), 400
        
        if not is_valid_facebook_url(url):
            return jsonify({'success': False, 'error': 'URL de Facebook no válida'}), 400
        
        # Intentar descargar el video
        video_path = download_reel(url)
        
        # Si no se encontró, buscar en temp
        if not video_path or not os.path.exists(video_path):
            logger.info("Buscando videos en directorio temporal...")
            video_path = find_video_in_temp()
            
            if video_path and os.path.exists(video_path):
                logger.info(f"Video encontrado en temp: {video_path}")
            else:
                return jsonify({'success': False, 'error': 'No se pudo descargar el video. Verifica que el enlace sea correcto y que el video sea público.'}), 500
        
        # Verificar que el archivo tenga un tamaño razonable
        if os.path.getsize(video_path) < 1000:  # Menos de 1KB
            logger.warning(f"Archivo demasiado pequeño: {video_path}")
            try:
                os.remove(video_path)
            except:
                pass
            return jsonify({'success': False, 'error': 'El archivo descargado está vacío o es demasiado pequeño'}), 500
        
        try:
            # Generar nombre de archivo
            original_filename = os.path.basename(video_path)
            name, ext = os.path.splitext(original_filename)
            
            # Limpiar el nombre
            clean_name = clean_filename(name)
            if not clean_name:
                clean_name = f"facebook_reel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            filename = f"{clean_name}{ext}"
            download_path = os.path.join(DOWNLOAD_PATH, filename)
            
            # Si ya existe, agregar número
            counter = 1
            base, ext = os.path.splitext(download_path)
            while os.path.exists(download_path):
                download_path = f"{base}_{counter}{ext}"
                counter += 1
            
            # Mover archivo a descargas
            logger.info(f"Moviendo archivo a: {download_path}")
            shutil.move(video_path, download_path)
            logger.info("Archivo movido exitosamente")
            
            return jsonify({
                'success': True,
                'message': 'Descarga exitosa',
                'filename': os.path.basename(download_path),
                'path': download_path
            })
            
        except Exception as e:
            logger.error(f"Error al mover archivo: {str(e)}")
            # Si falla, servir el archivo desde temp
            try:
                return send_file(
                    video_path,
                    as_attachment=True,
                    download_name=os.path.basename(video_path)
                )
            except Exception as send_error:
                logger.error(f"Error al enviar archivo: {send_error}")
                return jsonify({'success': False, 'error': f'Error al procesar el archivo: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Error general: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error al procesar la solicitud: {str(e)}'}), 500

@app.route('/test', methods=['GET'])
def test():
    """Endpoint de prueba para verificar que la aplicación funciona"""
    return jsonify({'status': 'ok', 'message': 'Aplicación funcionando correctamente'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
