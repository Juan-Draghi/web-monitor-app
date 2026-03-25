import streamlit as st
import asyncio
import hashlib
import json
import os
import time
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime, timedelta
from huggingface_hub import HfApi, hf_hub_download
import requests
from bs4 import BeautifulSoup

# Playwright browsers are now installed via Dockerfile at build time.
# No runtime installation needed.

# --- Helper Functions ---

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
PLAYWRIGHT_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
]
REQUEST_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept-Language": "es-419,es;q=0.9",
}
STATIC_REQUEST_DOMAINS = ("afcp.org.ar", "uade.edu.ar")
MONITOR_EXECUTOR = ThreadPoolExecutor(max_workers=1)
ACTIVE_MONITOR = {
    "future": None,
    "started_at": None,
}
MANUAL_REVIEW_INTERVAL_DAYS = 15
MANUAL_REVIEW_FILENAME = "manual_review_schedule.json"
MANUAL_REVIEW_URLS = (
    "https://adrianmercadorealestate.com/blog/informes",
    "https://www.colliers.com/es-ar",
    "https://www.fabianachaval.com/blog",
    "https://www.ljramos.com.ar/informes-del-mercado-inmobiliario",
    "https://www.cbre.com.ar/insights#market-reports",
)


def get_env_int(key, default, minimum=1):
    """Read a positive integer env var with a safe fallback."""
    try:
        return max(minimum, int(os.getenv(key, str(default))))
    except (TypeError, ValueError):
        return default

def get_secret(key):
    """Retrieves secret from Streamlit secrets or Environment Variables (for Docker)."""
    # 1. Try Streamlit Secrets (Native Spaces)
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass  # No secrets.toml found, continue to env vars
    # 2. Try Environment Variables (Docker Spaces)
    return os.getenv(key)

def load_urls():
    if os.path.exists("urls.txt"):
        with open("urls.txt", "r") as f:
            return [line.strip() for line in f if line.strip()]
    return []


def should_use_requests(url):
    """Return True for sites that are stable enough without Playwright."""
    return any(domain in url for domain in STATIC_REQUEST_DOMAINS)


def is_gdrive_folder(url):
    """Return True when the URL points to a public Google Drive folder."""
    return "drive.google.com/drive/folders/" in url


def set_active_monitor(future, started_at):
    """Persist the active monitor job across reruns and page reloads."""
    ACTIVE_MONITOR["future"] = future
    ACTIVE_MONITOR["started_at"] = started_at


def get_active_monitor():
    """Return the currently active monitor job, if any."""
    return ACTIVE_MONITOR["future"], ACTIVE_MONITOR["started_at"]

URLS_A_MONITOREAR = load_urls()
AUTO_MONITOR_URLS = [url for url in URLS_A_MONITOREAR if url not in MANUAL_REVIEW_URLS]
HASH_FILENAME = "web_monitoring_hashes.json"
REQUEST_TIMEOUT = get_env_int("REQUEST_TIMEOUT", 30)
PAGE_GOTO_TIMEOUT_MS = get_env_int("PAGE_GOTO_TIMEOUT_MS", 45000)
PAGE_IDLE_TIMEOUT_MS = get_env_int("PAGE_IDLE_TIMEOUT_MS", 3000)
PAGE_TEXT_TIMEOUT_MS = get_env_int("PAGE_TEXT_TIMEOUT_MS", 5000)
REQUEST_TEXT_MIN_CHARS = get_env_int("REQUEST_TEXT_MIN_CHARS", 80)
BATCH_SIZE = get_env_int("BATCH_SIZE", 1)
MAX_RETRIES = get_env_int("MAX_RETRIES", 2)


@lru_cache(maxsize=1)
def get_requests_session():
    """Reuse HTTP connections across requests to reduce startup overhead."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    return session

def get_hf_api():
    """Returns HF Api instance if secrets are configured."""
    token = get_secret("HF_TOKEN")
    if token:
        return HfApi(token=token)
    return None

@lru_cache(maxsize=1)
def load_hashes():
    """Loads hashes from HF Dataset (preferred) or local file."""
    dataset_id = get_secret("DATASET_ID")
    token = get_secret("HF_TOKEN")
    
    # Try loading from HF Hub first
    if dataset_id and token:
        try:
            file_path = hf_hub_download(
                repo_id=dataset_id,
                filename=HASH_FILENAME,
                repo_type="dataset",
                token=token
            )
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"No existing hashes found on HF Hub or error downloading: {e}")
            # Fallback will return empty dict if not found
            
    # Fallback to local file
    if os.path.exists(HASH_FILENAME):
        with open(HASH_FILENAME, "r") as f:
            return json.load(f)
            
    return {}

def save_hashes(hashes):
    """Saves hashes to HF Dataset (preferred) and local file."""
    # Save locally first
    with open(HASH_FILENAME, "w") as f:
        json.dump(hashes, f, indent=4)
        
    # Upload to HF Hub
    dataset_id = get_secret("DATASET_ID")
    api = get_hf_api()
    load_hashes.cache_clear()
    
    if dataset_id and api:
        try:
            api.upload_file(
                path_or_fileobj=HASH_FILENAME,
                path_in_repo=HASH_FILENAME,
                repo_id=dataset_id,
                repo_type="dataset",
                commit_message=f"Update hashes {datetime.now().isoformat()}"
            )
            return {
                "level": "success",
                "message": "Estado guardado en Hugging Face Dataset.",
            }
        except Exception as e:
            return {
                "level": "error",
                "message": f"Error guardando en HF Dataset: {e}",
            }
    else:
        return {
            "level": "warning",
            "message": "No se configuraron secretos HF_TOKEN/DATASET_ID. El estado no persistira al reiniciar.",
        }


@lru_cache(maxsize=1)
def load_manual_review_state():
    """Load the manual review reminder state from HF Dataset or local file."""
    dataset_id = get_secret("DATASET_ID")
    token = get_secret("HF_TOKEN")

    if dataset_id and token:
        try:
            file_path = hf_hub_download(
                repo_id=dataset_id,
                filename=MANUAL_REVIEW_FILENAME,
                repo_type="dataset",
                token=token,
            )
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception:
            pass

    if os.path.exists(MANUAL_REVIEW_FILENAME):
        with open(MANUAL_REVIEW_FILENAME, "r") as f:
            return json.load(f)

    return {"last_reviewed_at": None}


def save_manual_review_state(state):
    """Persist the manual review reminder state."""
    with open(MANUAL_REVIEW_FILENAME, "w") as f:
        json.dump(state, f, indent=4)

    dataset_id = get_secret("DATASET_ID")
    api = get_hf_api()
    load_manual_review_state.cache_clear()

    if dataset_id and api:
        try:
            api.upload_file(
                path_or_fileobj=MANUAL_REVIEW_FILENAME,
                path_in_repo=MANUAL_REVIEW_FILENAME,
                repo_id=dataset_id,
                repo_type="dataset",
                commit_message=f"Update manual review reminder {datetime.now().isoformat()}",
            )
            return {
                "level": "success",
                "message": "Recordatorio manual actualizado.",
            }
        except Exception as e:
            return {
                "level": "error",
                "message": f"Error guardando recordatorio manual: {e}",
            }

    return {
        "level": "warning",
        "message": "Recordatorio manual guardado solo en almacenamiento local.",
    }


def get_manual_review_status():
    """Compute whether the manual review reminder is due."""
    state = load_manual_review_state()
    last_reviewed_at = state.get("last_reviewed_at")

    if not last_reviewed_at:
        return {
            "due": True,
            "last_reviewed_at": None,
            "next_due_at": None,
            "days_until_due": 0,
        }

    reviewed_at = datetime.fromisoformat(last_reviewed_at)
    next_due_at = reviewed_at + timedelta(days=MANUAL_REVIEW_INTERVAL_DAYS)
    days_until_due = (next_due_at.date() - datetime.now().date()).days
    return {
        "due": datetime.now() >= next_due_at,
        "last_reviewed_at": reviewed_at,
        "next_due_at": next_due_at,
        "days_until_due": days_until_due,
    }

def clean_text(text):
    """Normalize text to reduce false positives due to whitespace."""
    return " ".join(text.split())

def calculate_hash(text):
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

# --- Zonaprop PDF pattern mapping ---
# Maps a Zonaprop blog URL to its PDF filename template.
# The template uses {year} and {month:02d} for the report date.
# Upload folder (year/month in path) can lag 0-2 months behind report date.
ZONAPROP_PDF_PATTERNS = {
    "zpindex/gba-oeste-sur-venta": "INDEX_GBA_OESTE_REPORTE_{year}-{month:02d}.pdf",
    "zpindex/gba-venta":           "INDEX_GBA_NORTE_REPORTE_{year}-{month:02d}.pdf",
    "zpindex/informe-demanda":     "INDEX_AMBA_REPORTE_DEMANDA-{year}-{month:02d}-PDF.pdf",
    "zpindex":                     "INDEX_CABA_REPORTE_{year}-{month:02d}.pdf",
}

def get_zonaprop_pdf_pattern(url):
    """Returns the PDF filename template for a given Zonaprop URL, or None."""
    for key, pattern in ZONAPROP_PDF_PATTERNS.items():
        if key in url:
            return pattern
    return None

def find_latest_zonaprop_pdf(pdf_pattern):
    """Probes wp-content/uploads with recent year/month combos to find the latest PDF.
    
    The upload folder date and report date can differ by up to 2 months.
    We try upload folders from today back 2 months, and for each folder
    try report months from that month back 3 months.
    Returns the URL of the first found PDF, or None.
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = get_requests_session()
    
    now = datetime.now()
    base_url = "https://www.zonaprop.com.ar/blog/wp-content/uploads"
    
    # Build candidate (upload_year, upload_month, report_year, report_month) combos.
    # Upload folder goes from current month back 2 months.
    # Report date goes from upload month back 3 months.
    candidates = []
    for upload_delta in range(5):  # 0=current month back to 4 months ago
        upload_month = now.month - upload_delta
        upload_year = now.year
        while upload_month < 1:
            upload_month += 12
            upload_year -= 1
        for report_delta in range(5):  # report can be 0-4 months before upload
            rep_month = upload_month - report_delta
            rep_year = upload_year
            while rep_month < 1:
                rep_month += 12
                rep_year -= 1
            candidates.append((upload_year, upload_month, rep_year, rep_month))
    
    # Deduplicate while preserving order (most recent first)
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)
    
    for upload_year, upload_month, rep_year, rep_month in unique_candidates:
        filename = pdf_pattern.format(year=rep_year, month=rep_month)
        pdf_url = f"{base_url}/{upload_year}/{upload_month:02d}/{filename}"
        try:
            r = session.head(pdf_url, timeout=10, verify=False, allow_redirects=True)
            if r.status_code == 200:
                return pdf_url
        except Exception:
            continue
    
    return None

def parse_gdrive_date(date_text):
    """Parse Google Drive modified dates in Spanish."""
    month_map = {
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12,
    }
    cleaned = date_text.strip().lower().replace(".", "")
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


def fetch_gdrive_folder(url):
    """Fetch a public Google Drive folder and return recent file metadata.

    The monitor uses the modified date plus file names of the most recent
    publications to detect updates without depending on a fixed naming scheme.
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = get_requests_session()
    
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, verify=False)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"

        soup = BeautifulSoup(response.text, "html.parser")
        entries = []

        for row in soup.select('tr[role="row"]'):
            name_el = row.select_one('td[data-column-field="6"] [data-tooltip]')
            date_el = row.select_one('td[data-column-field="5"] span')
            if not name_el or not date_el:
                continue

            file_name = name_el.get("data-tooltip", "").strip()
            file_name = file_name.removesuffix(" PDF").removesuffix(" PPTX").removesuffix(" PPT")
            modified_text = date_el.get_text(" ", strip=True)
            modified_dt = parse_gdrive_date(modified_text)
            if not file_name or modified_dt is None:
                continue

            entries.append(
                {
                    "name": file_name,
                    "modified_text": modified_text,
                    "modified_iso": modified_dt.date().isoformat(),
                }
            )

        if not entries:
            return None, "No se encontraron archivos con metadatos de fecha en la carpeta"

        deduped_entries = {
            (entry["name"], entry["modified_iso"]): entry
            for entry in entries
        }
        sorted_entries = sorted(
            deduped_entries.values(),
            key=lambda entry: (entry["modified_iso"], entry["name"]),
            reverse=True,
        )
        recent_entries = sorted_entries[:6]
        content_lines = [
            f'{entry["modified_iso"]}|{entry["modified_text"]}|{entry["name"]}'
            for entry in recent_entries
        ]
        return "\n".join(content_lines), ""
        
    except Exception as e:
        return None, str(e)

async def fetch_with_requests(url):
    """Fetches static content with a shared requests session."""
    session = get_requests_session()
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: session.get(url, timeout=REQUEST_TIMEOUT, verify=False),
    )
    return response


def extract_visible_text(html_content):
    """Extract visible text from HTML for hash comparison."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)


async def fetch_text_with_requests(url):
    """Try to fetch a page via requests and return visible text."""
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = await fetch_with_requests(url)
    if response.status_code != 200:
        return None, f"HTTP Error {response.status_code}"

    content = extract_visible_text(response.text)
    if len(content) < REQUEST_TEXT_MIN_CHARS:
        return None, "Contenido insuficiente (Requests)"

    return content, ""


async def fetch_with_playwright(browser, url):
    """Fallback fetch for pages that requests could not read reliably."""
    content = ""
    status = "Error"
    error_msg = ""

    if browser is None:
        return url, "Error", "", "Browser no disponible para esta URL"

    for attempt in range(MAX_RETRIES):
        context = None
        page = None
        try:
            context = await browser.new_context(
                user_agent=DEFAULT_USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                extra_http_headers={
                    "Accept-Language": "es-419,es;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Referer": "https://www.google.com/"
                }
            )

            page = await context.new_page()
            page.set_default_navigation_timeout(PAGE_GOTO_TIMEOUT_MS)
            page.set_default_timeout(PAGE_TEXT_TIMEOUT_MS)

            try:
                await page.goto(url, wait_until="domcontentloaded")
            except Exception:
                print(f"Timeout loading {url}, attempting capture anyway...")

            try:
                await page.wait_for_load_state("networkidle", timeout=PAGE_IDLE_TIMEOUT_MS)
            except Exception:
                pass

            content = await page.inner_text("body")

            if content:
                status = "Success"
                error_msg = ""
                break
            raise Exception("Empty content retrieved")

        except Exception as e:
            status = "Error"
            error_msg = str(e)
            print(f"Attempt {attempt+1} failed for {url}: {e}")

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

    return url, status, content, error_msg


async def get_or_launch_browser(playwright, browser_holder):
    """Launch Chromium lazily only if a fallback is really needed."""
    if browser_holder["browser"] is None:
        browser_holder["browser"] = await playwright.chromium.launch(
            headless=True,
            args=PLAYWRIGHT_LAUNCH_ARGS,
        )
    return browser_holder["browser"]


async def fetch_url(playwright, browser_holder, url):
    """Fetch key content using special cases, requests first, and Playwright only as fallback."""
    if "zonaprop.com.ar" in url:
        pdf_pattern = get_zonaprop_pdf_pattern(url)
        if pdf_pattern is None:
            return url, "Error", "", "URL de Zonaprop no reconocida (sin patrón PDF definido)"

        loop = asyncio.get_running_loop()
        pdf_url = await loop.run_in_executor(None, find_latest_zonaprop_pdf, pdf_pattern)

        if pdf_url:
            return url, "Success", f"PDF_URL: {pdf_url}", ""
        return url, "Error", "", "No se encontró PDF reciente (últimos 3 meses probados)"

    if is_gdrive_folder(url):
        content, error_msg = fetch_gdrive_folder(url)
        if content:
            return url, "Success", content, ""
        return url, "Error", "", error_msg or "No se pudo leer la carpeta de Google Drive"

    requests_error = ""
    try:
        content, requests_error = await fetch_text_with_requests(url)
        if content:
            return url, "Success", content, ""
    except Exception as e:
        requests_error = f"Requests Error: {str(e)}"

    browser = await get_or_launch_browser(playwright, browser_holder)
    playwright_result = await fetch_with_playwright(browser, url)
    if playwright_result[1] == "Success":
        return playwright_result

    if requests_error:
        return url, "Error", "", f"{requests_error} | Playwright: {playwright_result[3]}"
    return playwright_result

async def process_urls(urls, progress_callback=None):
    """Process URLs with requests-first scraping and lazy Playwright fallback."""
    results = []
    total = len(urls)
    if total == 0:
        if progress_callback:
            progress_callback(1.0, "No hay URLs configuradas.")
        return results
    
    async with async_playwright() as p:
        browser_holder = {"browser": None}
        try:
            batch_size = BATCH_SIZE
            for i in range(0, total, batch_size):
                batch = urls[i:i + batch_size]

                current_progress = i / total
                if progress_callback:
                    progress_callback(current_progress, f"Procesando lote {i//batch_size + 1}... ({i}/{total})")

                for url in batch:
                    results.append(await fetch_url(p, browser_holder, url))
        finally:
            if browser_holder["browser"] is not None:
                await browser_holder["browser"].close()
            
    if progress_callback:
        progress_callback(1.0, "Completado.")
    return results


def run_monitor_job(urls):
    """Run the monitor in a worker thread so Streamlit stays responsive."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        raw_results = loop.run_until_complete(process_urls(urls))
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    previous_hashes = load_hashes()
    new_hashes = previous_hashes.copy()
    processed_data = []

    changes_count = 0
    errors_count = 0

    for url, status, text, error_msg in raw_results:
        row = {
            "URL": url,
            "Estado": status,
            "Resultado": "Sin Cambios",
            "Error": error_msg if status == "Error" else "",
        }

        if status == "Success":
            cleaned_text = clean_text(text)
            current_hash = calculate_hash(cleaned_text)
            last_hash = previous_hashes.get(url)

            if last_hash is None:
                row["Resultado"] = "Nuevo (Primer Rastreo)"
                new_hashes[url] = current_hash
            elif current_hash != last_hash:
                row["Resultado"] = "CAMBIO DETECTADO"
                new_hashes[url] = current_hash
                changes_count += 1
            else:
                row["Resultado"] = "Sin Cambios"
        else:
            row["Resultado"] = "Error de Lectura"
            errors_count += 1

        processed_data.append(row)

    save_status = save_hashes(new_hashes)
    return {
        "processed_data": processed_data,
        "changes_count": changes_count,
        "errors_count": errors_count,
        "save_status": save_status,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }

# --- Streamlit UI ---

st.set_page_config(page_title="Web Monitor", layout="wide", page_icon="🕵️")

st.title("🕵️ Monitoreo de Sitios Web")

manual_review_status = get_manual_review_status()
if manual_review_status["due"]:
    st.warning(
        "Recordatorio de revision manual: toca revisar los sitios excluidos del monitoreo automatico."
    )
    with st.expander("Sitios para revision manual", expanded=True):
        st.write(
            f"Frecuencia: cada {MANUAL_REVIEW_INTERVAL_DAYS} dias. "
            "Estos sitios quedan fuera del scraping automatico por falsos positivos."
        )
        for url in MANUAL_REVIEW_URLS:
            st.write(f"- {url}")
        if st.button("Marcar revision manual como realizada hoy"):
            review_save_status = save_manual_review_state(
                {"last_reviewed_at": datetime.now().isoformat(timespec="seconds")}
            )
            if review_save_status["level"] == "success":
                st.success(review_save_status["message"])
            elif review_save_status["level"] == "warning":
                st.warning(review_save_status["message"])
            else:
                st.error(review_save_status["message"])
            st.rerun()
else:
    next_due_at = manual_review_status["next_due_at"].strftime("%Y-%m-%d")
    st.info(f"Proxima revision manual programada para {next_due_at}.")

# Secrets Status
if get_secret("HF_TOKEN") and get_secret("DATASET_ID"):
    st.sidebar.success("🔒 Persistencia Activa (Dataset Configurado)")
else:
    st.sidebar.warning("⚠️ Persistencia no configurada (Faltan Secretos)")

st.sidebar.header("Configuración")
st.sidebar.caption(f"URLs por lote: {BATCH_SIZE} | Reintentos por URL: {MAX_RETRIES}")
st.sidebar.caption(
    f"URLs automaticas: {len(AUTO_MONITOR_URLS)} | Revision manual: {len(MANUAL_REVIEW_URLS)}"
)

st.sidebar.caption(f"Timeout request: {REQUEST_TIMEOUT}s | goto: {PAGE_GOTO_TIMEOUT_MS//1000}s")

# --- Diagnostics ---
with st.sidebar.expander("🛠️ Diagnóstico", expanded=False):
    st.write("Estado de Secretos:")
    
    token_val = get_secret("HF_TOKEN")
    dataset_val = get_secret("DATASET_ID")
    
    token_status = "✅ Encontrado" if token_val else "❌ No encontrado"
    dataset_status = "✅ Encontrado" if dataset_val else "❌ No encontrado"
    
    st.write(f"HF_TOKEN: {token_status}")
    st.write(f"DATASET_ID: {dataset_status}")
    
    if st.button("Verificar Token y Acceso"):
        if not token_val:
            st.error("No hay token para probar.")
        else:
            try:
                api = HfApi(token=token_val)
                user_info = api.whoami()
                st.success(f"Token válido! Usuario: {user_info['name']}")
                
                # Check repo access
                if dataset_val:
                    try:
                        # Try to get dataset info
                        ds_info = api.dataset_info(repo_id=dataset_val)
                        st.success(f"Acceso al Dataset '{dataset_val}': {ds_info.private and 'Privado (OK)' or 'Público (OK)'}")
                    except Exception as e:
                        st.error(f"No se puede acceder al dataset '{dataset_val}'.\nError: {e}")
                else:
                    st.warning("DATASET_ID no definido.")
                    
            except Exception as e:
                st.error(f"Token inválido o error de conexión: {e}")

    st.write("---")
    st.write("Variables de Entorno Disponibles (Keys):")
    # Filter to avoid showing sensitive system vars, or just show keys
    env_keys = sorted(k for k in os.environ.keys() if "TOKEN" not in k and "SECRET" not in k)
    st.code(env_keys)

force_refresh = st.sidebar.button("Ejecutar Monitoreo Ahora")

# Status Area
status_placeholder = st.empty()
progress_bar = st.empty()
progress_text = st.empty()

# Persistent State for "Last Run"
if "last_results" not in st.session_state:
    st.session_state["last_results"] = None
if "monitor_future" not in st.session_state:
    st.session_state["monitor_future"] = None
if "monitor_started_at" not in st.session_state:
    st.session_state["monitor_started_at"] = None
if "last_run_summary" not in st.session_state:
    st.session_state["last_run_summary"] = None
if "last_save_status" not in st.session_state:
    st.session_state["last_save_status"] = None

current_future = st.session_state["monitor_future"]
active_future, active_started_at = get_active_monitor()
if current_future is None and active_future is not None:
    st.session_state["monitor_future"] = active_future
    st.session_state["monitor_started_at"] = active_started_at
    current_future = active_future

monitor_running = current_future is not None and not current_future.done()

if force_refresh and not monitor_running:
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["monitor_future"] = MONITOR_EXECUTOR.submit(run_monitor_job, tuple(AUTO_MONITOR_URLS))
    st.session_state["monitor_started_at"] = started_at
    st.session_state["last_save_status"] = None
    set_active_monitor(st.session_state["monitor_future"], started_at)
    current_future = st.session_state["monitor_future"]
    monitor_running = True

if monitor_running:
    status_placeholder.info(
        f"Monitoreo en curso desde {st.session_state['monitor_started_at']}. "
        "La pagina se actualiza sola cada 5 segundos."
    )
    progress_bar.progress(0.01)
    progress_text.text("Procesando URLs en segundo plano...")
    time.sleep(5)
    st.rerun()
elif current_future is not None and current_future.done():
    progress_bar.empty()
    progress_text.empty()
    try:
        job_result = current_future.result()
        st.session_state["last_results"] = job_result["processed_data"]
        st.session_state["last_run_summary"] = job_result
        st.session_state["last_save_status"] = job_result["save_status"]
        status_placeholder.success(
            f"Monitoreo completado. Cambios: {job_result['changes_count']} | "
            f"Errores: {job_result['errors_count']}"
        )
    except Exception as e:
        status_placeholder.error(f"Error ejecutando el monitoreo: {e}")
    finally:
        st.session_state["monitor_future"] = None
        st.session_state["monitor_started_at"] = None
        set_active_monitor(None, None)
else:
    progress_bar.empty()
    progress_text.empty()

save_status = st.session_state.get("last_save_status")
if save_status:
    if save_status["level"] == "success":
        st.sidebar.success(save_status["message"])
    elif save_status["level"] == "warning":
        st.sidebar.warning(save_status["message"])
    else:
        st.sidebar.error(save_status["message"])

st.caption(
    "El monitoreo automatico excluye algunos sitios con falsos positivos recurrentes. "
    "Esos casos quedan bajo revision manual periodica."
)

# Display Results
if st.session_state["last_results"]:
    df = pd.DataFrame(st.session_state["last_results"])
    
    # Styling the dataframe
    def color_status(val):
        color = 'white'
        if 'CAMBIO' in val:
            color = '#ffcccb' # Reddish
        elif 'Nuevo' in val:
            color = '#e0f7fa' # Cyanish
        elif 'Error' in val:
            color = '#fff3cd' # Yellowish
        return f'background-color: {color}; color: black'

    # Display Results grouped by category
    st.markdown("---")
    
    # Filter data
    df_changes = df[df["Resultado"].str.contains("CAMBIO") | df["Resultado"].str.contains("Nuevo")]
    df_errors = df[df["Estado"] == "Error"]
    df_no_changes = df[(df["Resultado"] == "Sin Cambios") & (df["Estado"] != "Error")]
    
    # 1. CHANGES (Highlighted)
    st.subheader(f"🚨 Sitios con Cambios ({len(df_changes)})")
    if not df_changes.empty:
        st.dataframe(
            df_changes.style.map(color_status, subset=['Resultado']),
            width="stretch",
            column_config={
                "URL": st.column_config.LinkColumn("Sitio Web"),
                "Error": st.column_config.TextColumn("Detalle Error", width="medium")
            }
        )
    else:
        st.info("No se detectaron cambios en esta ejecución.")

    # 2. ERRORS
    if not df_errors.empty:
        st.subheader(f"⚠️ Errores de Lectura ({len(df_errors)})")
        st.dataframe(
            df_errors,
            width="stretch",
            column_config={
                "URL": st.column_config.LinkColumn("Sitio Web"),
                "Error": st.column_config.TextColumn("Detalle Error", width="medium")
            }
        )

    # 3. NO CHANGES (Collapsible)
    with st.expander(f"✅ Sitios Sin Cambios ({len(df_no_changes)})", expanded=False):
        if not df_no_changes.empty:
            st.dataframe(
                df_no_changes,
                width="stretch",
                column_config={
                    "URL": st.column_config.LinkColumn("Sitio Web"),
                    "Error": st.column_config.TextColumn("Detalle Error", width="medium")
                }
            )
        else:
            st.write("No hay sitios sin cambios.")
else:
    st.info("Presiona 'Ejecutar Monitoreo Ahora' para comenzar.")

st.markdown("---")
st.caption("Nota: En Hugging Face Spaces free, los datos guardados se pueden perder si la aplicación se reinicia. Para persistencia real, configura un Dataset o base de datos externa.")
