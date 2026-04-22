import json
import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from monitor import RESULTS_FILE, URLS_FILE, load_urls, run_monitor

# ── Path handling: dev vs ejecutable PyInstaller ────────────────────────────
# sys._MEIPASS  → donde PyInstaller extrajo los assets (templates, static)
# sys.executable.parent → carpeta del .exe, donde se guardan los datos
if getattr(sys, 'frozen', False):
    _BUNDLE_DIR = Path(sys._MEIPASS)
    _APP_DIR    = Path(sys.executable).parent
    app = Flask(
        __name__,
        template_folder=str(_BUNDLE_DIR / 'templates'),
        static_folder=str(_BUNDLE_DIR / 'static'),
    )
    # Log de errores junto al ejecutable (sin consola visible)
    logging.basicConfig(
        filename=str(_APP_DIR / 'monitoreo_error.log'),
        level=logging.ERROR,
        format='%(asctime)s %(levelname)s %(message)s',
    )
else:
    app = Flask(__name__)

_state_lock = threading.Lock()
_state = {
    'running': False,
    'current': 0,
    'total': 0,
    'url': '',
    'playwright_available': None,
    'playwright_message': '',
    'finished_at': '',
}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run():
    with _state_lock:
        if _state['running']:
            return jsonify({'error': 'Ya hay una corrida en curso'}), 409
        _state['running'] = True
        _state['current'] = 0
        _state['total'] = len(load_urls())
        _state['url'] = ''
        _state['playwright_available'] = None
        _state['playwright_message'] = ''
        _state['finished_at'] = ''

    def worker():
        def on_progress(current, total, url):
            with _state_lock:
                _state['current'] = current
                _state['total'] = total
                _state['url'] = url

        def on_playwright_status(available, msg):
            with _state_lock:
                _state['playwright_available'] = available
                _state['playwright_message'] = msg

        try:
            run_monitor(
                on_progress=on_progress,
                on_playwright_status=on_playwright_status,
            )
        except Exception:
            pass
        finally:
            with _state_lock:
                _state['running'] = False
                _state['finished_at'] = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/status')
def status():
    with _state_lock:
        return jsonify(dict(_state))


@app.route('/results')
def results():
    if not RESULTS_FILE.exists():
        return jsonify({'results': [], 'generated_at': ''})
    data = json.loads(RESULTS_FILE.read_text(encoding='utf-8'))
    return jsonify(data)


@app.route('/urls', methods=['GET'])
def get_urls():
    urls = load_urls()
    return jsonify({'urls': urls})


@app.route('/urls', methods=['POST'])
def save_urls():
    with _state_lock:
        if _state['running']:
            return jsonify({'error': 'No se puede editar mientras hay una corrida en curso'}), 409
    data = request.get_json()
    urls = [u.strip() for u in data.get('urls', []) if u.strip()]
    URLS_FILE.write_text('\n'.join(urls) + '\n', encoding='utf-8')
    return jsonify({'saved': len(urls)})


def _open_browser():
    time.sleep(1.2)
    webbrowser.open('http://localhost:5000')


if __name__ == '__main__':
    try:
        threading.Thread(target=_open_browser, daemon=True).start()
        app.run(port=5000, debug=False, use_reloader=False)
    except Exception as exc:
        logging.exception('Error al iniciar el servidor')
        # Mostrar cuadro de error en Windows cuando no hay consola visible
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f'No se pudo iniciar MonitoreoWeb:\n\n{exc}\n\n'
                f'Revisá monitoreo_error.log para más detalles.',
                'MonitoreoWeb — Error',
                0x10,  # MB_ICONERROR
            )
        except Exception:
            pass
