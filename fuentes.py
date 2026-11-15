"""Altas, bajas y modificaciones de fuentes con historial obligatorio.

Cada cambio en `urls.txt` se hace de a uno, con motivo, y queda registrado en
`historial_fuentes.md` (Markdown legible por personas y agentes).

Coherencia entre los dos archivos:
1. Se preparan los borradores del `urls.txt` nuevo y del historial con el
   registro agregado. Si algo falla, no se toca ningún archivo real.
2. Se reemplaza `urls.txt` y después el historial.
3. Si falla el reemplazo del historial, se restaura el `urls.txt` anterior y se
   informa que el cambio no se aplicó. Nunca se informa como hecho un cambio
   que no quedó registrado.
"""

import re
from datetime import datetime

import monitor

HISTORY_FILE = monitor.BASE_DIR / 'historial_fuentes.md'

HISTORY_HEADER = (
    '# Historial de fuentes\n'
    '\n'
    'Registro de altas, bajas y modificaciones de las fuentes monitoreadas '
    '(`urls.txt`).\n'
    'Lo escribe la aplicación Monitor web: no editar a mano. Cada cambio '
    'incluye su motivo.\n'
    'Este archivo se publica en GitHub junto con el proyecto.\n'
)

ACTION_INVENTORY = 'Inventario inicial'
ACTION_ADD = 'Alta'
ACTION_REMOVE = 'Baja'
ACTION_UPDATE = 'Modificación'
EXTERNAL_SUFFIX = ' (fuera de la aplicación)'
ACTION_ADD_EXTERNAL = ACTION_ADD + EXTERNAL_SUFFIX
ACTION_REMOVE_EXTERNAL = ACTION_REMOVE + EXTERNAL_SUFFIX

ENTRY_TITLE_RE = re.compile(r'^## \d{4}-\d{2}-\d{2} \d{2}:\d{2} · (.+)$')


class HistoryFormatError(Exception):
    """El historial no se puede interpretar (por ejemplo, si se editó a mano)."""


class SourceError(Exception):
    """Pedido inválido: no se aplicó ningún cambio. El mensaje es para la persona."""


class SourceSaveError(Exception):
    """Fallo al guardar: no se aplicó ningún cambio. El mensaje es para la persona."""


def _now():
    return datetime.now()


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------

def clean_reason(reason):
    """Motivo en una sola línea; vacío si no se indicó."""
    return ' '.join(str(reason or '').split())


def clean_url(url):
    return str(url or '').strip()


def validate_reason(reason):
    reason = clean_reason(reason)
    if not reason:
        raise SourceError('Indicá el motivo del cambio. Sin motivo no se guarda nada.')
    return reason


def validate_url(url):
    url = clean_url(url)
    if not url:
        raise SourceError('Indicá la URL.')
    if any(char.isspace() for char in url):
        raise SourceError('La URL no puede contener espacios.')
    if not (url.startswith('http://') or url.startswith('https://')) or len(url) <= len('https://'):
        raise SourceError('La URL debe empezar con http:// o https://.')
    return url


# ---------------------------------------------------------------------------
# Formato del historial
# ---------------------------------------------------------------------------

def _entry_title(action, now):
    return f'## {now.strftime("%Y-%m-%d %H:%M")} · {action}'


def format_inventory_entry(urls, now):
    lines = [
        _entry_title(ACTION_INVENTORY, now),
        '- Motivo: Inicio del historial con las fuentes vigentes en urls.txt.',
        f'- Fuentes ({len(urls)}):',
    ]
    lines.extend(f'  - {url}' for url in urls)
    return '\n'.join(lines) + '\n'


def format_change_entry(action, url, reason, now, previous_url=None, manual_followup=None):
    lines = [_entry_title(action, now), f'- URL: {url}']
    if previous_url:
        lines.append(f'- URL anterior: {previous_url}')
    lines.append(f'- Motivo: {reason}')
    if manual_followup is not None:
        answer = 'sí' if manual_followup else 'no'
        lines.append(f'- Seguimiento manual fuera de la aplicación: {answer}')
    return '\n'.join(lines) + '\n'


def _append_entry(history_text, entry):
    return history_text.rstrip('\n') + '\n\n' + entry


# ---------------------------------------------------------------------------
# Lectura y guardado
# ---------------------------------------------------------------------------

def _urls_text(urls):
    return '\n'.join(urls) + '\n' if urls else ''


def read_history():
    if HISTORY_FILE.exists():
        return HISTORY_FILE.read_text(encoding='utf-8')
    return ''


def ensure_history(now=None):
    """Crea el historial con el inventario inicial si todavía no existe."""
    if HISTORY_FILE.exists():
        return False
    text = _append_entry(HISTORY_HEADER, format_inventory_entry(monitor.load_urls(), now or _now()))
    targets = [HISTORY_FILE]
    try:
        temp_path = monitor._write_temp_text(HISTORY_FILE, text)
        monitor._replace_file(temp_path, HISTORY_FILE)
    except OSError as exc:
        raise SourceSaveError(f'No se pudo crear el historial de fuentes: {exc}') from exc
    finally:
        monitor._remove_temp_files(targets)
    return True


def _save_change(new_urls, entry):
    """Guarda juntos el urls.txt nuevo y el registro del historial."""
    urls_file = monitor.URLS_FILE
    previous_urls_text = urls_file.read_text(encoding='utf-8') if urls_file.exists() else ''
    new_history_text = _append_entry(read_history(), entry)
    targets = [urls_file, HISTORY_FILE]

    try:
        # Paso 1: borradores. Ante un error, los archivos reales quedan intactos.
        try:
            urls_temp = monitor._write_temp_text(urls_file, _urls_text(new_urls))
            history_temp = monitor._write_temp_text(HISTORY_FILE, new_history_text)
        except OSError as exc:
            raise SourceSaveError(f'No se pudo guardar el cambio; no se aplicó. Detalle: {exc}') from exc

        # Paso 2: primero urls.txt, después el historial.
        try:
            monitor._replace_file(urls_temp, urls_file)
        except OSError as exc:
            raise SourceSaveError(f'No se pudo guardar urls.txt; el cambio no se aplicó. Detalle: {exc}') from exc

        try:
            monitor._replace_file(history_temp, HISTORY_FILE)
        except OSError as exc:
            _restore_urls(urls_file, previous_urls_text)
            raise SourceSaveError(
                'No se pudo registrar el cambio en el historial; se restauró la lista '
                f'anterior y el cambio no se aplicó. Detalle: {exc}'
            ) from exc
    finally:
        monitor._remove_temp_files(targets)


def _restore_urls(urls_file, previous_text):
    temp_path = monitor._write_temp_text(urls_file, previous_text)
    monitor._replace_file(temp_path, urls_file)


# ---------------------------------------------------------------------------
# Operaciones
# ---------------------------------------------------------------------------

def add_source(url, reason, now=None):
    url = validate_url(url)
    reason = validate_reason(reason)
    ensure_history(now)
    urls = monitor.load_urls()
    if url in urls:
        raise SourceError('Esa URL ya está en la lista de fuentes.')
    entry = format_change_entry(ACTION_ADD, url, reason, now or _now())
    new_urls = urls + [url]
    _save_change(new_urls, entry)
    return new_urls


def remove_source(url, reason, manual_followup=False, now=None):
    url = clean_url(url)
    reason = validate_reason(reason)
    ensure_history(now)
    urls = monitor.load_urls()
    if url not in urls:
        raise SourceError('Esa URL no está en la lista de fuentes.')
    entry = format_change_entry(
        ACTION_REMOVE, url, reason, now or _now(), manual_followup=bool(manual_followup)
    )
    new_urls = [item for item in urls if item != url]
    _save_change(new_urls, entry)
    return new_urls


def _parse_entries(text):
    """Separa el historial en registros con su acción y sus URLs."""
    entries = []
    current = None
    for line in text.splitlines():
        match = ENTRY_TITLE_RE.match(line)
        if match:
            current = {'action': match.group(1).strip(), 'url': None,
                       'previous_url': None, 'inventory': []}
            entries.append(current)
        elif current is None:
            continue
        elif line.startswith('- URL anterior: '):
            current['previous_url'] = line[len('- URL anterior: '):].strip()
        elif line.startswith('- URL: '):
            current['url'] = line[len('- URL: '):].strip()
        elif line.startswith('  - '):
            current['inventory'].append(line[len('  - '):].strip())
    return entries


def expected_urls_from_history(text):
    """Reconstruye la lista de fuentes aplicando, en orden, cada registro."""
    urls = []
    for entry in _parse_entries(text):
        action, url = entry['action'], entry['url']
        if action == ACTION_INVENTORY:
            urls = list(entry['inventory'])
        elif action in (ACTION_ADD, ACTION_ADD_EXTERNAL) and url:
            if url not in urls:
                urls.append(url)
        elif action in (ACTION_REMOVE, ACTION_REMOVE_EXTERNAL) and url:
            urls = [item for item in urls if item != url]
        elif action == ACTION_UPDATE and url and entry['previous_url']:
            urls = [url if item == entry['previous_url'] else item for item in urls]
            if url not in urls:
                urls.append(url)
        else:
            raise HistoryFormatError(f'Registro no reconocido en el historial: «{action}».')
    return urls


def detect_external_changes():
    """Compara urls.txt con lo que indica el historial.

    Devuelve las fuentes agregadas y quitadas directamente en el archivo (a
    mano o desde GitHub), que todavía no tienen motivo registrado.
    """
    ensure_history()
    expected = expected_urls_from_history(read_history())
    actual = monitor.load_urls()
    return {
        'added': [url for url in actual if url not in expected],
        'removed': [url for url in expected if url not in actual],
    }


def register_external_changes(changes, now=None):
    """Registra en el historial los cambios hechos fuera de la aplicación.

    `changes` es una lista de {'url', 'tipo': 'alta'|'baja', 'motivo'}. Debe
    coincidir exactamente con lo detectado ahora: si el archivo cambió desde
    que se mostró el aviso, no se registra nada. No modifica urls.txt.
    """
    detected = detect_external_changes()
    expected_pairs = {('alta', url) for url in detected['added']}
    expected_pairs |= {('baja', url) for url in detected['removed']}

    submitted = []
    for change in changes or []:
        kind = str(change.get('tipo', ''))
        url = clean_url(change.get('url'))
        submitted.append((kind, url, validate_reason(change.get('motivo'))))

    if not expected_pairs:
        raise SourceError('No hay cambios externos pendientes de registrar.')
    if {(kind, url) for kind, url, _ in submitted} != expected_pairs or len(submitted) != len(expected_pairs):
        raise SourceError('La lista de fuentes cambió desde que se mostró el aviso. '
                          'Recargá la página y volvé a intentarlo.')

    timestamp = now or _now()
    history_text = read_history()
    for kind, url, reason in submitted:
        action = ACTION_ADD_EXTERNAL if kind == 'alta' else ACTION_REMOVE_EXTERNAL
        history_text = _append_entry(history_text, format_change_entry(action, url, reason, timestamp))

    targets = [HISTORY_FILE]
    try:
        temp_path = monitor._write_temp_text(HISTORY_FILE, history_text)
        monitor._replace_file(temp_path, HISTORY_FILE)
    except OSError as exc:
        raise SourceSaveError(f'No se pudo registrar en el historial; no se guardó nada. Detalle: {exc}') from exc
    finally:
        monitor._remove_temp_files(targets)
    return monitor.load_urls()


def update_source(previous_url, new_url, reason, now=None):
    previous_url = clean_url(previous_url)
    new_url = validate_url(new_url)
    reason = validate_reason(reason)
    ensure_history(now)
    urls = monitor.load_urls()
    if previous_url not in urls:
        raise SourceError('La URL que querés modificar no está en la lista de fuentes.')
    if new_url == previous_url:
        raise SourceError('La URL nueva es igual a la anterior; no hay cambio para registrar.')
    if new_url in urls:
        raise SourceError('La URL nueva ya está en la lista de fuentes.')
    entry = format_change_entry(
        ACTION_UPDATE, new_url, reason, now or _now(), previous_url=previous_url
    )
    new_urls = [new_url if item == previous_url else item for item in urls]
    _save_change(new_urls, entry)
    return new_urls
