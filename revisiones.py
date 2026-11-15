"""Revisión de URLs sin cambios detectados.

Guarda en `revisiones_urls.json` el resultado de la revisión manual de cada URL.
Las corridas sólo leen este archivo; por eso una revisión hecha mientras corre
el monitoreo no se pierde.

Estados posibles de una URL:
- "normal": se monitorea y, si pasan 30 días sin cambios, aparece en
  «Revisión por antigüedad». `ultima_revision` (si existe) es la fecha desde la
  que se cuenta el plazo cuando es posterior al último cambio detectado.
- "a_revisar": la persona indicó que hubo cambios que la aplicación no detectó.
- "inactivo": la persona indicó que el sitio parece inactivo o caído.

En "a_revisar" e "inactivo" la URL se sigue monitoreando, pero no vuelve a la
revisión por antigüedad hasta que se marque como resuelta.
"""

import json
import logging
import threading
from datetime import datetime

import monitor

REVIEWS_FILE = monitor.BASE_DIR / 'revisiones_urls.json'

STATE_NORMAL = 'normal'
STATE_TO_REVIEW = 'a_revisar'
STATE_INACTIVE = 'inactivo'
CLASSIFIED_STATES = (STATE_TO_REVIEW, STATE_INACTIVE)

_reviews_lock = threading.Lock()


class ReviewError(Exception):
    """Pedido inválido: no se guardó nada. El mensaje es para la persona."""


def _now():
    return datetime.now()


def _timestamp(now):
    return now.isoformat(timespec='seconds')


def load_reviews():
    if not REVIEWS_FILE.exists():
        return {}
    try:
        return json.loads(REVIEWS_FILE.read_text(encoding='utf-8'))
    except ValueError:
        # Un archivo dañado no debe impedir el monitoreo; se informa en el log.
        logging.warning('revisiones_urls.json no se pudo leer; se ignora.')
        return {}


def _save_reviews(reviews):
    targets = [REVIEWS_FILE]
    try:
        temp_path = monitor._write_temp_json(REVIEWS_FILE, reviews)
        monitor._replace_file(temp_path, REVIEWS_FILE)
    finally:
        monitor._remove_temp_files(targets)


def _require_listed_url(url):
    url = str(url or '').strip()
    if url not in monitor.load_urls():
        raise ReviewError('Esa URL no está en la lista de fuentes.')
    return url


def _clean_note(note):
    return ' '.join(str(note or '').split())


def _update(url, change):
    """Aplica `change(registro_actual) -> registro_nuevo` y guarda."""
    with _reviews_lock:
        reviews = load_reviews()
        reviews[url] = change(dict(reviews.get(url, {})))
        _save_reviews(reviews)
        return reviews[url]


# ---------------------------------------------------------------------------
# Operaciones
# ---------------------------------------------------------------------------

def confirm_no_news(url, now=None):
    """R1: la persona confirmó que no hubo novedades. El plazo vuelve a contar."""
    url = _require_listed_url(url)
    stamp = _timestamp(now or _now())
    return _update(url, lambda record: {
        'estado': STATE_NORMAL,
        'ultima_revision': stamp,
    })


def classify(url, state, note='', now=None):
    """R2 y R3: cambios no detectados o sitio inactivo/caído."""
    url = _require_listed_url(url)
    if state not in CLASSIFIED_STATES:
        raise ReviewError('Clasificación no reconocida.')
    stamp = _timestamp(now or _now())

    def change(record):
        record.update({'estado': state, 'clasificada_el': stamp, 'nota': _clean_note(note)})
        return record
    return _update(url, change)


def resolve(url, now=None):
    """Cierra una URL clasificada: vuelve al monitoreo normal y el plazo cuenta desde hoy."""
    url = _require_listed_url(url)
    stamp = _timestamp(now or _now())

    def change(record):
        if record.get('estado') not in CLASSIFIED_STATES:
            raise ReviewError('Esa URL no está en «URLs a revisar» ni en «Sitios inactivos o caídos».')
        return {'estado': STATE_NORMAL, 'ultima_revision': stamp}
    return _update(url, change)


# ---------------------------------------------------------------------------
# Datos para la pantalla
# ---------------------------------------------------------------------------

def is_excluded_from_stale_review(record):
    return record.get('estado') in CLASSIFIED_STATES


def filter_pending_review_items(review_items, generated_at, reviews=None):
    """Quita de la última corrida las URLs revisadas o clasificadas después de ella.

    Así una URL desaparece de «Revisión por antigüedad» en el momento en que se
    revisa, sin esperar a la corrida siguiente.
    """
    reviews = load_reviews() if reviews is None else reviews
    pending = []
    for item in review_items:
        record = reviews.get(item.get('URL'), {})
        if is_excluded_from_stale_review(record):
            continue
        reviewed_at = record.get('ultima_revision') or ''
        if generated_at and reviewed_at > generated_at:
            continue
        pending.append(item)
    return pending


def classified_items(state, urls=None, reviews=None, metadata=None):
    """URLs en «URLs a revisar» o «Sitios inactivos o caídos», con datos de apoyo."""
    urls = monitor.load_urls() if urls is None else urls
    reviews = load_reviews() if reviews is None else reviews
    metadata = monitor.load_metadata() if metadata is None else metadata
    items = []
    for url in urls:
        record = reviews.get(url, {})
        if record.get('estado') != state:
            continue
        info = metadata.get(url, {})
        items.append({
            'URL': url,
            'ClasificadaEl': record.get('clasificada_el', ''),
            'Nota': record.get('nota', ''),
            'UltimaLecturaExitosa': info.get('last_success_at', ''),
            'UltimoCambio': info.get('last_change_at') or info.get('first_seen_at', ''),
            'UltimoEstado': info.get('last_status', ''),
        })
    return sorted(items, key=lambda item: item['ClasificadaEl'])
