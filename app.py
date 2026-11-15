import json
import logging
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from monitor import (
    RESULTS_FILE,
    URLS_FILE,
    RunCancelled,
    load_urls,
    run_monitor,
)
import fuentes
import revisiones

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
_cancel_event = threading.Event()
_state = {
    'running': False,
    'cancel_requested': False,
    'run_state': 'idle',
    'message': '',
    'current': 0,
    'total': 0,
    'url': '',
    'playwright_available': None,
    'playwright_message': '',
    'started_at': '',
    'last_progress_at': '',
    'finished_at': '',
}


def _timestamp():
    return datetime.now().isoformat(timespec='seconds')


# ── Aviso de repetición ─────────────────────────────────────────────────────
# Si la última corrida completada terminó hace menos de este plazo, pedir
# confirmación antes de iniciar otra. Exactamente al cumplirse el plazo ya no
# se avisa. Las corridas canceladas o fallidas no cuentan: no guardan
# resultados, así que no cambian la hora de referencia.
REPEAT_WARNING_MINUTES = 60


def _now():
    return datetime.now()


def get_last_completed_at():
    """Hora en que se guardó la última corrida completada, o None si no hay."""
    try:
        data = json.loads(RESULTS_FILE.read_text(encoding='utf-8'))
        return datetime.fromisoformat(data.get('generated_at') or '')
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def get_repeat_warning(now=None):
    """Devuelve los datos del aviso si corresponde mostrarlo; si no, None."""
    last_completed_at = get_last_completed_at()
    if last_completed_at is None:
        return None
    elapsed = (now or _now()) - last_completed_at
    if elapsed >= timedelta(minutes=REPEAT_WARNING_MINUTES):
        return None
    return {
        'last_completed_at': last_completed_at.isoformat(timespec='seconds'),
        'minutes_since': max(0, int(elapsed.total_seconds() // 60)),
        'threshold_minutes': REPEAT_WARNING_MINUTES,
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run', methods=['POST'])
def run():
    body = request.get_json(silent=True) or {}
    confirm_repeat = body.get('confirm_repeat') is True

    with _state_lock:
        if _state['running']:
            return jsonify({'error': 'Ya hay una corrida en curso'}), 409
        if not confirm_repeat:
            warning = get_repeat_warning()
            if warning:
                # No se inicia nada ni se toca ningún archivo hasta que la
                # persona confirme desde la interfaz.
                return jsonify({'confirmation_required': True, **warning}), 409
        _cancel_event.clear()
        _state['running'] = True
        _state['cancel_requested'] = False
        _state['run_state'] = 'running'
        _state['message'] = 'Monitoreo en curso.'
        _state['current'] = 0
        _state['total'] = len(load_urls())
        _state['url'] = ''
        _state['playwright_available'] = None
        _state['playwright_message'] = ''
        _state['started_at'] = _timestamp()
        _state['last_progress_at'] = _state['started_at']
        _state['finished_at'] = ''

    def worker():
        def on_progress(current, total, url):
            with _state_lock:
                _state['current'] = current
                _state['total'] = total
                _state['url'] = url
                _state['last_progress_at'] = _timestamp()

        def on_playwright_status(available, msg):
            with _state_lock:
                _state['playwright_available'] = available
                _state['playwright_message'] = msg

        try:
            run_monitor(
                on_progress=on_progress,
                on_playwright_status=on_playwright_status,
                should_cancel=_cancel_event.is_set,
            )
            outcome = 'completed'
            message = 'Corrida finalizada.'
        except RunCancelled:
            outcome = 'cancelled'
            message = 'Corrida cancelada. Se conservaron los resultados anteriores.'
        except Exception as exc:
            logging.exception('La corrida de monitoreo se interrumpió')
            outcome = 'failed'
            message = f'La corrida se interrumpió: {exc}'
        finally:
            with _state_lock:
                _state['running'] = False
                _state['cancel_requested'] = False
                _state['run_state'] = outcome
                _state['message'] = message
                _state['url'] = ''
                _state['finished_at'] = _timestamp()
            _cancel_event.clear()

    threading.Thread(target=worker, name='web-monitor-run', daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/cancel', methods=['POST'])
def cancel():
    with _state_lock:
        if not _state['running']:
            return jsonify({'error': 'No hay una corrida en curso'}), 409
        _cancel_event.set()
        _state['cancel_requested'] = True
        _state['run_state'] = 'cancelling'
        _state['message'] = 'Cancelación solicitada. Cerrando la fuente actual…'
        return jsonify({'status': 'cancelling'}), 202


@app.route('/status')
def status():
    with _state_lock:
        return jsonify(dict(_state))


@app.route('/results')
def results():
    if RESULTS_FILE.exists():
        data = json.loads(RESULTS_FILE.read_text(encoding='utf-8'))
    else:
        data = {'results': [], 'generated_at': '', 'review_items': []}
    # Las revisiones manuales se aplican en el momento, sin esperar otra corrida.
    reviews = revisiones.load_reviews()
    data['review_items'] = revisiones.filter_pending_review_items(
        data.get('review_items') or [], data.get('generated_at') or '', reviews
    )
    urls = load_urls()
    data['to_review_items'] = revisiones.classified_items(revisiones.STATE_TO_REVIEW, urls, reviews)
    data['inactive_items'] = revisiones.classified_items(revisiones.STATE_INACTIVE, urls, reviews)
    return jsonify(data)


# ── Revisión de URLs sin cambios ─────────────────────────────────────────────
# Se guarda en revisiones_urls.json, que las corridas sólo leen: por eso se
# permite revisar también mientras corre el monitoreo.

def _apply_review(operation):
    try:
        record = operation()
    except revisiones.ReviewError as exc:
        return jsonify({'error': str(exc)}), 400
    except OSError as exc:
        logging.exception('No se pudo guardar una revisión de URL')
        return jsonify({'error': f'No se pudo guardar la revisión; no se aplicó. Detalle: {exc}'}), 500
    return jsonify({'review': record})


@app.route('/reviews/confirm', methods=['POST'])
def review_confirm():
    body = request.get_json(silent=True) or {}
    return _apply_review(lambda: revisiones.confirm_no_news(body.get('url')))


@app.route('/reviews/classify', methods=['POST'])
def review_classify():
    body = request.get_json(silent=True) or {}
    return _apply_review(
        lambda: revisiones.classify(body.get('url'), body.get('estado'), body.get('nota'))
    )


@app.route('/reviews/resolve', methods=['POST'])
def review_resolve():
    body = request.get_json(silent=True) or {}
    return _apply_review(lambda: revisiones.resolve(body.get('url')))


@app.route('/urls', methods=['GET'])
def get_urls():
    urls = load_urls()
    return jsonify({'urls': urls, 'file': str(URLS_FILE)})


# ── Cambios de fuentes: de a uno, con motivo obligatorio ────────────────────
# No existe un guardado de la lista completa: cada alta, baja o modificación
# queda registrada en historial_fuentes.md (ver fuentes.py).

def _apply_source_change(operation, block_during_run=True):
    # Se mantiene el bloqueo durante el cambio para que no pueda arrancar una
    # corrida a mitad de camino.
    with _state_lock:
        if block_during_run and _state['running']:
            return jsonify({'error': 'No se pueden modificar fuentes mientras hay una corrida en curso.'}), 409
        try:
            urls = operation()
        except fuentes.HistoryFormatError as exc:
            return jsonify({'error': f'No se pudo interpretar historial_fuentes.md: {exc}'}), 500
        except fuentes.SourceError as exc:
            return jsonify({'error': str(exc)}), 400
        except fuentes.SourceSaveError as exc:
            logging.exception('No se pudo guardar un cambio de fuentes')
            return jsonify({'error': str(exc)}), 500
        except OSError as exc:
            logging.exception('Error de archivos al cambiar fuentes')
            return jsonify({'error': f'No se pudo completar el cambio: {exc}'}), 500
    return jsonify({'urls': urls, 'file': str(URLS_FILE)})


# ── Cambios hechos fuera de la aplicación (a mano o desde GitHub) ──────────
# Se detectan comparando urls.txt con el historial. No se bloquea el
# monitoreo: la corrida usa urls.txt tal como está. Registrar sólo agrega
# los motivos al historial; no modifica urls.txt.

@app.route('/urls/external-changes', methods=['GET'])
def get_external_changes():
    with _state_lock:
        try:
            changes = fuentes.detect_external_changes()
        except fuentes.HistoryFormatError as exc:
            return jsonify({'error': f'No se pudo interpretar historial_fuentes.md: {exc}'}), 500
        except (fuentes.SourceSaveError, OSError) as exc:
            logging.exception('No se pudieron comparar las fuentes con el historial')
            return jsonify({'error': str(exc)}), 500
    changes['pending'] = bool(changes['added'] or changes['removed'])
    return jsonify(changes)


@app.route('/urls/external-changes', methods=['POST'])
def register_external_changes():
    body = request.get_json(silent=True) or {}
    return _apply_source_change(
        lambda: fuentes.register_external_changes(body.get('changes')),
        block_during_run=False,
    )


@app.route('/urls/add', methods=['POST'])
def add_url():
    body = request.get_json(silent=True) or {}
    return _apply_source_change(
        lambda: fuentes.add_source(body.get('url'), body.get('motivo'))
    )


@app.route('/urls/remove', methods=['POST'])
def remove_url():
    body = request.get_json(silent=True) or {}
    return _apply_source_change(
        lambda: fuentes.remove_source(
            body.get('url'), body.get('motivo'), body.get('seguimiento_manual') is True
        )
    )


@app.route('/urls/update', methods=['POST'])
def update_url():
    body = request.get_json(silent=True) or {}
    return _apply_source_change(
        lambda: fuentes.update_source(body.get('url_anterior'), body.get('url'), body.get('motivo'))
    )


def _open_browser():
    time.sleep(1.2)
    webbrowser.open('http://localhost:5000')


if __name__ == '__main__':
    try:
        # Primera vez: crear el historial con el inventario de fuentes vigente.
        fuentes.ensure_history()
    except Exception:
        logging.exception('No se pudo crear el historial de fuentes')
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
