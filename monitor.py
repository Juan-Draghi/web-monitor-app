import asyncio
import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
except Exception:
    async_playwright = None


import os as _os
import sys as _sys


def resolve_base_dir():
    """Devuelve la carpeta unica donde se leen y guardan los datos."""
    if not getattr(_sys, 'frozen', False):
        return Path(__file__).parent

    executable_dir = Path(_sys.executable).parent
    project_dir = executable_dir.parent.parent
    project_urls = project_dir / 'urls.txt'

    if executable_dir.name == 'MonitoreoWeb' and executable_dir.parent.name == 'dist':
        if project_urls.exists():
            return project_dir

    return executable_dir


# Cuando corre como ejecutable PyInstaller (frozen):
# - Los datos (urls.txt, resultados) se guardan junto al .exe
# - El Playwright empaquetado busca el browser en una ruta interna; hay que
#   redirigirlo a %LOCALAPPDATA%\ms-playwright donde instalar.bat lo instaló.
if getattr(_sys, 'frozen', False):
    _local_appdata = _os.environ.get('LOCALAPPDATA', '')
    if _local_appdata:
        _os.environ.setdefault(
            'PLAYWRIGHT_BROWSERS_PATH',
            _os.path.join(_local_appdata, 'ms-playwright'),
        )
BASE_DIR = resolve_base_dir()

URLS_FILE = BASE_DIR / 'urls.txt'
HASHES_FILE = BASE_DIR / 'web_monitoring_hashes.json'
METADATA_FILE = BASE_DIR / 'web_monitoring_metadata.json'
RESULTS_FILE = BASE_DIR / 'last_run_results.json'

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

REQUEST_HEADERS = {
    'User-Agent': DEFAULT_USER_AGENT,
    'Accept-Language': 'es-419,es;q=0.9',
}

PLAYWRIGHT_LAUNCH_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--no-sandbox',
]

REQUEST_TIMEOUT = 30
PAGE_GOTO_TIMEOUT_MS = 45000
PAGE_IDLE_TIMEOUT_MS = 3000
PAGE_TEXT_TIMEOUT_MS = 5000
REQUEST_TEXT_MIN_CHARS = 80
STALE_REVIEW_DAYS = 30
URL_PROCESS_TIMEOUT_SECONDS = 120
CANCEL_POLL_INTERVAL_SECONDS = 0.25
PLAYWRIGHT_CLOSE_TIMEOUT_SECONDS = 5
PLAYWRIGHT_LAUNCH_TIMEOUT_SECONDS = 30


class RunCancelled(Exception):
    """Indica una cancelación solicitada por la persona usuaria."""


async def _await_quietly(awaitable, timeout=PLAYWRIGHT_CLOSE_TIMEOUT_SECONDS):
    """Espera una limpieza asíncrona sin permitir que bloquee la corrida."""
    try:
        await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass



# Dominios que usan Playwright como método primario (contenido dinámico o bloquean requests).
# Se aplica extractor de títulos para evitar falsos positivos por ads/widgets.
PLAYWRIGHT_PRIMARY_DOMAINS = (
    'adrianmercadorealestate.com',
    'fabianachaval.com',
    'ljramos.com.ar',
    'cbre.com.ar',
)

STATIC_REQUEST_DOMAINS = ('afcp.org.ar', 'uade.edu.ar')

ZONAPROP_PDF_PATTERNS = {
    'zpindex/gba-oeste-venta': 'INDEX_GBA_OESTE_REPORTE_{year}-{month:02d}.pdf',
    'zpindex/gba-sur-venta': 'INDEX_GBA_SUR_REPORTE_{year}-{month:02d}.pdf',
    'zpindex/gba-venta': 'INDEX_GBA_NORTE_REPORTE_{year}-{month:02d}.pdf',
    'zpindex/informe-demanda': 'INDEX_AMBA_REPORTE_DEMANDA-{year}-{month:02d}-PDF.pdf',
    'zpindex': 'INDEX_CABA_REPORTE_{year}-{month:02d}.pdf',
}


# ---------------------------------------------------------------------------
# Utilidades de persistencia
# ---------------------------------------------------------------------------

def load_urls():
    if not URLS_FILE.exists():
        URLS_FILE.write_text('', encoding='utf-8')
    return [
        line.strip()
        for line in URLS_FILE.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def save_urls(urls):
    clean_urls = [url.strip() for url in urls if url.strip()]
    URLS_FILE.write_text('\n'.join(clean_urls) + '\n', encoding='utf-8')
    return len(clean_urls)


def clean_text(text):
    return ' '.join(text.split())


def calculate_hash(text):
    if not text:
        return None
    return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()


def extract_visible_text(html_content):
    if not html_content:
        return ''
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator=' ', strip=True)


def extract_article_titles(html_content):
    """Extrae solo títulos de artículos/posts para evitar falsos positivos.

    Elimina elementos ruidosos (nav, footer, ads, widgets) y busca títulos
    en contenedores de artículos. Retorna cadena vacía si no encuentra nada,
    lo que indica al llamador que use el texto completo como fallback.
    """
    if not html_content:
        return ''
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.select(
        'header, footer, nav, aside, '
        '[class*="sidebar"], [class*="widget"], '
        '[class*="ad-"], [id*="sidebar"], [id*="footer"]'
    ):
        tag.decompose()

    selectors = [
        'article h2', 'article h3',
        '.post-title', '.entry-title', '.blog-post-title',
        'main h2', 'main h3',
        '[class*="post"] h2', '[class*="post"] h3',
        '[class*="blog"] h2', '[class*="blog"] h3',
    ]
    titles = []
    for sel in selectors:
        for el in soup.select(sel):
            text = el.get_text(strip=True)
            if text and len(text) > 5:
                titles.append(text)

    if not titles:
        return ''
    return '\n'.join(sorted(set(titles)))


def load_hashes():
    if HASHES_FILE.exists():
        return json.loads(HASHES_FILE.read_text(encoding='utf-8'))
    return {}


def load_metadata():
    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text(encoding='utf-8'))
    return {}


def save_hashes(hashes):
    HASHES_FILE.write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def save_metadata(metadata):
    METADATA_FILE.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def days_since(value, now):
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return None
    return (now - parsed).days


def update_url_metadata(metadata, url, status, result, error_msg, now):
    now_text = now.isoformat(timespec='seconds')
    current = metadata.get(url, {})

    current.setdefault('first_seen_at', now_text)
    current['last_status'] = status
    current['last_result'] = result
    current['last_error'] = error_msg if status == 'Error' else ''

    if status == 'Success':
        current['last_success_at'] = now_text
        current['consecutive_error_runs'] = 0

        if result in ('Nuevo (primer rastreo)', 'Cambio detectado'):
            current['last_change_at'] = now_text
            current['consecutive_unchanged_runs'] = 0
        else:
            current['consecutive_unchanged_runs'] = (
                int(current.get('consecutive_unchanged_runs', 0)) + 1
            )
    else:
        current['consecutive_error_runs'] = (
            int(current.get('consecutive_error_runs', 0)) + 1
        )

    metadata[url] = current


def build_review_items(metadata, urls, now, stale_days=STALE_REVIEW_DAYS):
    review_items = []
    for url in urls:
        item = metadata.get(url, {})
        if item.get('last_status') != 'Success':
            continue

        last_change_at = item.get('last_change_at') or item.get('first_seen_at')
        elapsed_days = days_since(last_change_at, now)
        if elapsed_days is None or elapsed_days < stale_days:
            continue

        review_items.append({
            'URL': url,
            'DiasDesdeUltimoCambio': elapsed_days,
            'UltimoCambio': last_change_at,
            'UltimaLecturaExitosa': item.get('last_success_at', ''),
            'CorridasSinCambios': int(item.get('consecutive_unchanged_runs', 0)),
            'Motivo': f'Sin cambios detectados hace {elapsed_days} dias',
        })

    return sorted(
        review_items,
        key=lambda row: row['DiasDesdeUltimoCambio'],
        reverse=True,
    )


def save_results(results, review_items=None):
    payload = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'results': results,
        'review_items': review_items or [],
    }
    RESULTS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

def get_requests_session():
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    return session


# ---------------------------------------------------------------------------
# Estrategias especiales: Zonaprop y Google Drive
# ---------------------------------------------------------------------------

def is_gdrive_folder(url):
    return 'drive.google.com/drive/folders/' in url


def get_zonaprop_pdf_pattern(url):
    for key, pattern in ZONAPROP_PDF_PATTERNS.items():
        if key in url:
            return pattern
    return None


def fetch_zonaprop_pdf_from_page(url, session):
    import urllib3
    from urllib.parse import urljoin

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, verify=False)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        pdf_links = []
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            text = link.get_text(' ', strip=True).lower()
            if '.pdf' not in href.lower():
                continue
            absolute_url = urljoin(url, href)
            score = 0
            if 'descarg' in text or 'informe' in text:
                score += 2
            if 'index' in absolute_url.lower() or 'reporte' in absolute_url.lower():
                score += 1
            pdf_links.append((score, absolute_url))
        if not pdf_links:
            return None
        pdf_links.sort(reverse=True)
        return pdf_links[0][1]
    except Exception:
        return None


def find_latest_zonaprop_pdf(pdf_pattern, session):
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    now = datetime.now()
    base_url = 'https://www.zonaprop.com.ar/blog/wp-content/uploads'
    candidates = []
    for report_delta in range(4):
        report_month = now.month - report_delta
        report_year = now.year
        while report_month < 1:
            report_month += 12
            report_year -= 1
        for upload_offset in range(3):
            upload_month = report_month + upload_offset
            upload_year = report_year
            while upload_month > 12:
                upload_month -= 12
                upload_year += 1
            candidates.append((upload_year, upload_month, report_year, report_month))

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)

    for upload_year, upload_month, report_year, report_month in unique_candidates:
        filename = pdf_pattern.format(year=report_year, month=report_month)
        pdf_url = f'{base_url}/{upload_year}/{upload_month:02d}/{filename}'
        try:
            response = session.head(pdf_url, timeout=3, verify=False, allow_redirects=True)
            if response.status_code == 200:
                return pdf_url
        except Exception:
            continue
    return None



async def fetch_gdrive_folder_playwright(browser, url):
    """Obtiene la lista de archivos de una carpeta pública de Google Drive.

    Google Drive renderiza el listado con JavaScript, por lo que requests
    siempre devuelve una página vacía. Playwright ejecuta el JS y espera
    a que aparezcan los nombres de archivo antes de extraerlos.
    """
    if browser is None:
        return url, 'Error', '', 'Requiere Playwright para leer carpetas de Drive'

    context = None
    page = None
    try:
        context = await browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={'Accept-Language': 'es-419,es;q=0.9'},
        )
        page = await context.new_page()
        page.set_default_navigation_timeout(PAGE_GOTO_TIMEOUT_MS)

        await page.goto(url, wait_until='domcontentloaded')

        # Esperar a que Drive renderice la grilla de archivos
        for selector in ('[data-tooltip]', '[role="gridcell"]', 'c-wiz'):
            try:
                await page.wait_for_selector(selector, timeout=8000)
                break
            except Exception:
                continue

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        names = set()

        # Estrategia 1: atributo data-tooltip (nombres de archivos en Drive)
        for el in soup.select('[data-tooltip]'):
            tooltip = el.get('data-tooltip', '').strip()
            # Excluir tooltips que son URLs, botones de UI o muy cortos
            if (tooltip and len(tooltip) > 3
                    and not tooltip.startswith('http')
                    and not tooltip.startswith('Compartir')
                    and not tooltip.startswith('Más')):
                names.add(tooltip)

        # Estrategia 2: texto de celdas de grilla (vista lista)
        if len(names) < 2:
            for el in soup.select('[role="gridcell"] span'):
                text = el.get_text(strip=True)
                if text and len(text) > 3:
                    names.add(text)

        if not names:
            return url, 'Error', '', (
                'No se encontraron archivos. La carpeta puede estar vacía, '
                'requerir inicio de sesión, o Drive cambió su estructura HTML.'
            )

        content = '\n'.join(sorted(names))
        return url, 'Success', content, ''

    except Exception as exc:
        return url, 'Error', '', f'Drive error: {exc}'
    finally:
        if page:
            await _await_quietly(page.close())
        if context:
            await _await_quietly(context.close())


# ---------------------------------------------------------------------------
# Fetch con requests
# ---------------------------------------------------------------------------

async def fetch_text_with_requests(session, url):
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: session.get(url, timeout=REQUEST_TIMEOUT, verify=False),
    )
    if response.status_code != 200:
        return None, f'HTTP Error {response.status_code}'
    content = extract_visible_text(response.text)
    if len(content) < REQUEST_TEXT_MIN_CHARS:
        return None, 'Contenido insuficiente (Requests)'
    return content, ''


# ---------------------------------------------------------------------------
# Fetch con Playwright
# ---------------------------------------------------------------------------

async def _playwright_get_html(browser, url):
    """Abre la URL con Playwright y devuelve el HTML crudo del body."""
    context = None
    page = None
    try:
        context = await browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={
                'Accept-Language': 'es-419,es;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': 'https://www.google.com/',
            },
        )
        page = await context.new_page()
        page.set_default_navigation_timeout(PAGE_GOTO_TIMEOUT_MS)
        page.set_default_timeout(PAGE_TEXT_TIMEOUT_MS)
        try:
            await page.goto(url, wait_until='domcontentloaded')
        except Exception:
            pass
        try:
            await page.wait_for_load_state('networkidle', timeout=PAGE_IDLE_TIMEOUT_MS)
        except Exception:
            pass
        html = await page.content()
        return html, ''
    except Exception as exc:
        return None, str(exc)
    finally:
        if page:
            await _await_quietly(page.close())
        if context:
            await _await_quietly(context.close())


async def fetch_with_playwright_smart(browser, url):
    """Fetch con Playwright + extractor de títulos para dominios ruidosos."""
    for _ in range(2):
        html, error = await _playwright_get_html(browser, url)
        if html:
            # Intentar extractor de artículos primero
            content = extract_article_titles(html)
            if not content:
                # Fallback a texto completo si no se detectaron artículos
                content = extract_visible_text(html)
            if content and len(content) >= REQUEST_TEXT_MIN_CHARS:
                return url, 'Success', content, ''
    return url, 'Error', '', error or 'Playwright: contenido vacío'


async def fetch_with_playwright_fallback(browser, url):
    """Fetch con Playwright como fallback (texto completo, sin extractor de artículos)."""
    if browser is None:
        return url, 'Error', '', 'Browser no disponible'

    error_msg = ''
    for _ in range(2):
        html, error_msg = await _playwright_get_html(browser, url)
        if html:
            content = extract_visible_text(html)
            if content:
                return url, 'Success', content, ''
    return url, 'Error', '', error_msg or 'Playwright: contenido vacío'


# ---------------------------------------------------------------------------
# Router principal de fetch
# ---------------------------------------------------------------------------

async def fetch_url(session, url, browser=None):
    # Zonaprop: lógica especial para encontrar PDFs
    if 'zonaprop.com.ar' in url:
        loop = asyncio.get_running_loop()
        # Primero buscar el PDF en la página (método rápido y directo)
        pdf_url = await loop.run_in_executor(None, fetch_zonaprop_pdf_from_page, url, session)
        # Si la página no devolvió el link (ej. carga con JS), intentar con Playwright
        if not pdf_url and browser is not None:
            html, _ = await _playwright_get_html(browser, url)
            if html:
                from urllib.parse import urljoin
                from bs4 import BeautifulSoup as _BS
                soup = _BS(html, 'html.parser')
                links = [
                    (urljoin(url, a['href']), a.get_text(' ', strip=True).lower())
                    for a in soup.find_all('a', href=True)
                    if '.pdf' in a['href'].lower()
                ]
                if links:
                    pdf_url = sorted(
                        links,
                        key=lambda t: (
                            ('descarg' in t[1] or 'informe' in t[1]),
                            ('index' in t[0].lower() or 'reporte' in t[0].lower()),
                        ),
                        reverse=True,
                    )[0][0]
        if pdf_url:
            return url, 'Success', f'PDF_URL: {pdf_url}', ''
        return url, 'Error', '', 'No se encontró PDF en la página'

    # Google Drive: usa Playwright para renderizar el listado de archivos
    if is_gdrive_folder(url):
        return await fetch_gdrive_folder_playwright(browser, url)

    # Dominios que necesitan Playwright como método primario
    if any(domain in url for domain in PLAYWRIGHT_PRIMARY_DOMAINS):
        if browser is not None:
            return await fetch_with_playwright_smart(browser, url)
        # Sin browser disponible, intentar requests de todas formas
        try:
            content, err = await fetch_text_with_requests(session, url)
            if content:
                return url, 'Success', content, ''
        except Exception as exc:
            err = str(exc)
        return url, 'Error', '', f'Requiere Playwright (no disponible). Requests: {err}'

    # Método primario: requests
    requests_error = ''
    try:
        content, requests_error = await fetch_text_with_requests(session, url)
        if content:
            return url, 'Success', content, ''
    except Exception as exc:
        requests_error = f'Requests Error: {exc}'

    # Fallback: Playwright (si está disponible y no es un dominio estático conocido)
    if browser is not None and not any(d in url for d in STATIC_REQUEST_DOMAINS):
        result = await fetch_with_playwright_fallback(browser, url)
        if result[1] == 'Success':
            return result
        combined_error = f'{requests_error} | Playwright: {result[3]}'
        return url, 'Error', '', combined_error

    return url, 'Error', '', requests_error or 'No se pudo leer la URL'


# ---------------------------------------------------------------------------
# Procesamiento batch
# ---------------------------------------------------------------------------

async def _cancel_task(task):
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=PLAYWRIGHT_CLOSE_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


async def _fetch_url_with_controls(
    session,
    url,
    browser,
    should_cancel,
    timeout=URL_PROCESS_TIMEOUT_SECONDS,
):
    task = asyncio.create_task(fetch_url(session, url, browser=browser))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while True:
        if should_cancel():
            await _cancel_task(task)
            raise RunCancelled()

        remaining = deadline - loop.time()
        if remaining <= 0:
            await _cancel_task(task)
            return (
                url,
                'Error',
                '',
                f'Tiempo máximo de {timeout:g} segundos excedido. '
                'La fuente requiere revisión manual.',
            )

        done, _ = await asyncio.wait(
            {task},
            timeout=min(CANCEL_POLL_INTERVAL_SECONDS, remaining),
        )
        if task not in done:
            continue

        try:
            return task.result()
        except Exception as exc:
            return url, 'Error', '', f'Error inesperado: {exc}'


async def process_urls(
    urls,
    on_progress=None,
    on_playwright_status=None,
    should_cancel=None,
    per_url_timeout=URL_PROCESS_TIMEOUT_SECONDS,
):
    session = get_requests_session()
    results = []
    should_cancel = should_cancel or (lambda: False)

    browser = None
    playwright_manager = None
    playwright_instance = None

    try:
        if should_cancel():
            raise RunCancelled()

        # Siempre lanzar Playwright: necesario para los dominios primarios.
        if async_playwright is None:
            if on_playwright_status:
                on_playwright_status(
                    False,
                    'Paquete playwright no instalado. Re-ejecutá instalar.bat.',
                )
        else:
            try:
                playwright_manager = async_playwright()
                playwright_instance = await asyncio.wait_for(
                    playwright_manager.__aenter__(),
                    timeout=PLAYWRIGHT_LAUNCH_TIMEOUT_SECONDS,
                )
                browser = await asyncio.wait_for(
                    playwright_instance.chromium.launch(
                        headless=True,
                        args=PLAYWRIGHT_LAUNCH_ARGS,
                    ),
                    timeout=PLAYWRIGHT_LAUNCH_TIMEOUT_SECONDS,
                )
                if on_playwright_status:
                    on_playwright_status(True, '')
            except Exception as exc:
                browser = None
                if on_playwright_status:
                    on_playwright_status(
                        False,
                        f'No se pudo iniciar Chromium: {exc}. Re-ejecutá instalar.bat.',
                    )

        for index, url in enumerate(urls, start=1):
            if should_cancel():
                raise RunCancelled()
            if on_progress:
                on_progress(index - 1, len(urls), url)

            result = await _fetch_url_with_controls(
                session,
                url,
                browser,
                should_cancel,
                timeout=per_url_timeout,
            )
            results.append(result)

        if should_cancel():
            raise RunCancelled()
        if on_progress:
            on_progress(len(urls), len(urls), '')
        return results
    finally:
        session.close()
        if browser:
            await _await_quietly(browser.close())
        if playwright_manager:
            await _await_quietly(
                playwright_manager.__aexit__(None, None, None)
            )


def run_monitor(
    on_progress=None,
    on_playwright_status=None,
    should_cancel=None,
    per_url_timeout=URL_PROCESS_TIMEOUT_SECONDS,
):
    should_cancel = should_cancel or (lambda: False)
    urls = load_urls()
    previous_hashes = load_hashes()
    metadata = load_metadata()
    run_started_at = datetime.now()
    new_hashes = previous_hashes.copy()

    raw_results = asyncio.run(
        process_urls(
            urls,
            on_progress=on_progress,
            on_playwright_status=on_playwright_status,
            should_cancel=should_cancel,
            per_url_timeout=per_url_timeout,
        )
    )
    if should_cancel():
        raise RunCancelled()

    processed_data = []
    for url, status, text, error_msg in raw_results:
        if should_cancel():
            raise RunCancelled()
        row = {
            'URL': url,
            'Estado': status,
            'Resultado': 'Sin cambios',
            'Error': error_msg if status == 'Error' else '',
        }
        if status == 'Success':
            current_hash = calculate_hash(clean_text(text))
            last_hash = previous_hashes.get(url)
            if last_hash is None:
                row['Resultado'] = 'Nuevo (primer rastreo)'
                new_hashes[url] = current_hash
            elif current_hash != last_hash:
                row['Resultado'] = 'Cambio detectado'
                new_hashes[url] = current_hash
            else:
                row['Resultado'] = 'Sin cambios'
        else:
            row['Resultado'] = 'Error de lectura'
        update_url_metadata(
            metadata, url, status, row['Resultado'], row['Error'], run_started_at
        )
        processed_data.append(row)

    review_items = build_review_items(metadata, urls, run_started_at)
    if should_cancel():
        raise RunCancelled()
    save_hashes(new_hashes)
    save_metadata(metadata)
    save_results(processed_data, review_items)
    return processed_data


