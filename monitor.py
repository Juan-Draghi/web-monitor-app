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

# Cuando corre como ejecutable PyInstaller (frozen):
# - Los datos (urls.txt, resultados) se guardan junto al .exe
# - El Playwright empaquetado busca el browser en una ruta interna; hay que
#   redirigirlo a %LOCALAPPDATA%\ms-playwright donde instalar.bat lo instaló.
if getattr(_sys, 'frozen', False):
    BASE_DIR = Path(_sys.executable).parent
    _local_appdata = _os.environ.get('LOCALAPPDATA', '')
    if _local_appdata:
        _os.environ.setdefault(
            'PLAYWRIGHT_BROWSERS_PATH',
            _os.path.join(_local_appdata, 'ms-playwright'),
        )
else:
    BASE_DIR = Path(__file__).parent

URLS_FILE = BASE_DIR / 'urls.txt'
HASHES_FILE = BASE_DIR / 'web_monitoring_hashes.json'
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
    return [
        line.strip()
        for line in URLS_FILE.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


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


def save_hashes(hashes):
    HASHES_FILE.write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )


def save_results(results):
    payload = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'results': results,
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


def parse_gdrive_date(date_text):
    month_map = {
        'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
        'sept': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    }
    cleaned = date_text.strip().lower().replace('.', '')
    parts = cleaned.split()
    if len(parts) != 3:
        return None
    day, month_text, year = parts
    month = month_map.get(month_text)
    if month is None:
        return None
    try:
        return datetime(int(year), month, int(day))
    except ValueError:
        return None


def fetch_gdrive_folder(url, session):
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, verify=False)
        if response.status_code != 200:
            return None, f'HTTP {response.status_code}'
        soup = BeautifulSoup(response.text, 'html.parser')
        entries = []
        for row in soup.select('tr[role="row"]'):
            name_el = row.select_one('td[data-column-field="6"] [data-tooltip]')
            date_el = row.select_one('td[data-column-field="5"] span')
            if not name_el or not date_el:
                continue
            file_name = name_el.get('data-tooltip', '').strip()
            file_name = file_name.removesuffix(' PDF').removesuffix(' PPTX').removesuffix(' PPT')
            modified_text = date_el.get_text(' ', strip=True)
            modified_dt = parse_gdrive_date(modified_text)
            if not file_name or modified_dt is None:
                continue
            entries.append({
                'name': file_name,
                'modified_text': modified_text,
                'modified_iso': modified_dt.date().isoformat(),
            })
        if not entries:
            return None, 'No se encontraron archivos con metadatos de fecha en la carpeta'
        deduped = {(e['name'], e['modified_iso']): e for e in entries}
        sorted_entries = sorted(
            deduped.values(),
            key=lambda e: (e['modified_iso'], e['name']),
            reverse=True,
        )
        content = '\n'.join(
            f"{e['modified_iso']}|{e['modified_text']}|{e['name']}"
            for e in sorted_entries[:6]
        )
        return content, ''
    except Exception as exc:
        return None, str(exc)


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
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass


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

    # Google Drive: lógica especial para listar archivos
    if is_gdrive_folder(url):
        loop = asyncio.get_running_loop()
        content, error = await loop.run_in_executor(None, fetch_gdrive_folder, url, session)
        if content:
            return url, 'Success', content, ''
        return url, 'Error', '', error

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

async def process_urls(urls, on_progress=None, on_playwright_status=None):
    session = get_requests_session()
    results = []

    browser = None
    playwright_ctx = None

    # Siempre lanzar Playwright: necesario para los dominios primarios
    if async_playwright is None:
        if on_playwright_status:
            on_playwright_status(False, 'Paquete playwright no instalado. Re-ejecutá instalar.bat.')
    else:
        try:
            playwright_ctx = await async_playwright().__aenter__()
            browser = await playwright_ctx.chromium.launch(
                headless=True, args=PLAYWRIGHT_LAUNCH_ARGS
            )
            if on_playwright_status:
                on_playwright_status(True, '')
        except Exception as exc:
            browser = None
            if on_playwright_status:
                on_playwright_status(False, f'No se pudo iniciar Chromium: {exc}. Re-ejecutá instalar.bat.')

    try:
        for index, url in enumerate(urls, start=1):
            if on_progress:
                on_progress(index - 1, len(urls), url)
            result = await fetch_url(session, url, browser=browser)
            results.append(result)
        if on_progress:
            on_progress(len(urls), len(urls), '')
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright_ctx:
            try:
                await playwright_ctx.__aexit__(None, None, None)
            except Exception:
                pass

    return results


def run_monitor(on_progress=None, on_playwright_status=None):
    urls = load_urls()
    previous_hashes = load_hashes()
    new_hashes = previous_hashes.copy()

    raw_results = asyncio.run(
        process_urls(urls, on_progress=on_progress, on_playwright_status=on_playwright_status)
    )

    processed_data = []
    for url, status, text, error_msg in raw_results:
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
        processed_data.append(row)

    save_hashes(new_hashes)
    save_results(processed_data)
    return processed_data


