import streamlit as st
import asyncio
import hashlib
import json
import os
from playwright.async_api import async_playwright
import pandas as pd
from datetime import datetime
import nest_asyncio
from huggingface_hub import HfApi, hf_hub_download
import requests
from bs4 import BeautifulSoup

# Apply nest_asyncio to allow nested event loops (crucial for Streamlit/Colab)
nest_asyncio.apply()

# Playwright browsers are now installed via Dockerfile at build time.
# No runtime installation needed.

# --- Helper Functions ---

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

URLS_A_MONITOREAR = load_urls()
HASH_FILENAME = "web_monitoring_hashes.json"

def get_hf_api():
    """Returns HF Api instance if secrets are configured."""
    token = get_secret("HF_TOKEN")
    if token:
        return HfApi(token=token)
    return None

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
    
    if dataset_id and api:
        try:
            api.upload_file(
                path_or_fileobj=HASH_FILENAME,
                path_in_repo=HASH_FILENAME,
                repo_id=dataset_id,
                repo_type="dataset",
                commit_message=f"Update hashes {datetime.now().isoformat()}"
            )
            st.toast("✅ Estado guardado en Hugging Face Dataset!")
        except Exception as e:
            st.error(f"Error guardando en HF Dataset: {e}")
    else:
        st.warning("⚠️ No se configuraron secretos HF_TOKEN/DATASET_ID. El estado no persistirá al reiniciar.")

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
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
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
            r = requests.head(pdf_url, headers=headers, timeout=10, verify=False)
            if r.status_code == 200:
                return pdf_url
        except Exception:
            continue
    
    return None

async def fetch_url(playwright, url):
    """Fetches key content from a URL using Requests (Static) or Playwright (Dynamic)."""
    content = ""
    status = "Error"
    error_msg = ""
    
    # 1. SPECIAL CASE: AFCP (Static/Requests preferred by user)
    # The user confirmed BeautifulSoup works, which implies standard HTTP get is enough.
    # We use requests to avoid browser overhead/timeouts for this specific site.
    if "afcp.org.ar" in url:
        try:
            # Suppress SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            # Run blocking requests in default executor
            loop = asyncio.get_running_loop()
            # Disable SSL verify as it often causes hang-ups on misconfigured servers/Wix
            response = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, timeout=60, verify=False))
            
            if response.status_code == 200:
                # Use BS4 to parse
                soup = BeautifulSoup(response.text, 'html.parser')
                content = soup.get_text(separator=' ', strip=True)
                
                if content:
                    return url, "Success", content, ""
                else:
                    return url, "Error", "", "Contenido vacío (Requests)"
            else:
                 return url, "Error", "", f"HTTP Error {response.status_code}"
                
        except Exception as e:
            return url, "Error", "", f"Requests Error: {str(e)}"

    # 2. SPECIAL CASE: Zonaprop (direct PDF HEAD request, bypasses Cloudflare)
    if "zonaprop.com.ar" in url:
        pdf_pattern = get_zonaprop_pdf_pattern(url)
        if pdf_pattern is None:
            return url, "Error", "", "URL de Zonaprop no reconocida (sin patrón PDF definido)"
        
        loop = asyncio.get_running_loop()
        pdf_url = await loop.run_in_executor(None, find_latest_zonaprop_pdf, pdf_pattern)
        
        if pdf_url:
            return url, "Success", f"PDF_URL: {pdf_url}", ""
        else:
            return url, "Error", "", "No se encontró PDF reciente (últimos 3 meses probados)"

    # 3. STANDARD CASE: Playwright (Other URLs)
    for attempt in range(3): # Try up to 3 times
        browser = None
        context = None
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            # Setup context with better headers for bot evasion
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                extra_http_headers={
                    "Accept-Language": "es-419,es;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Referer": "https://www.google.com/"
                }
            )
            
            page = await context.new_page()
            
            # Standard Logic
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except:
                print(f"Timeout loading {url}, attempting capture anyway...")
            
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass 
            content = await page.inner_text("body")

            if content:
                status = "Success"
                error_msg = ""
                break # Success, exit retry loop
            else:
                raise Exception("Empty content retrieved")
            
        except Exception as e:
            status = "Error"
            error_msg = str(e)
            print(f"Attempt {attempt+1} failed for {url}: {e}")
            
        finally:
            if context:
                try: await context.close()
                except: pass
            if browser:
                try: await browser.close()
                except: pass
                
    return url, status, content, error_msg

async def process_urls(urls, progress_bar, status_text):
    """Runs Playwright to fetch all URLs with progress tracking."""
    results = []
    total = len(urls)
    
    async with async_playwright() as p:
        batch_size = 5
        for i in range(0, total, batch_size):
            batch = urls[i:i + batch_size]
            
            # Update status
            current_progress = i / total
            progress_bar.progress(current_progress)
            status_text.text(f"Procesando lote {i//batch_size + 1}... ({i}/{total})")
            
            tasks = [fetch_url(p, url) for url in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
    progress_bar.progress(1.0)
    status_text.text("¡Completado!")
    return results

# --- Streamlit UI ---

st.set_page_config(page_title="Web Monitor", layout="wide", page_icon="🕵️")

st.title("🕵️ Monitoreo de Sitios Web")

# Secrets Status
if get_secret("HF_TOKEN") and get_secret("DATASET_ID"):
    st.sidebar.success("🔒 Persistencia Activa (Dataset Configurado)")
else:
    st.sidebar.warning("⚠️ Persistencia no configurada (Faltan Secretos)")

st.sidebar.header("Configuración")

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
    env_keys = [k for k in os.environ.keys()]
    st.code(env_keys)

force_refresh = st.sidebar.button("Ejecutar Monitoreo Ahora")

# Status Area
status_placeholder = st.empty()
progress_bar = st.empty()
progress_text = st.empty()

# Persistent State for "Last Run"
if "last_results" not in st.session_state:
    st.session_state["last_results"] = None

if force_refresh:
    status_placeholder.info("⏳ Iniciando navegador y proceso...")
    
    # Initialize UI elements
    bar = progress_bar.progress(0.0)
    txt = progress_text.text("Preparando...")
    
    # Run the async loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    raw_results = loop.run_until_complete(process_urls(URLS_A_MONITOREAR, bar, txt))
    
    # Process results
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
            "Error": error_msg if status == "Error" else ""
        }
        
        if status == "Success":
            cleaned_text = clean_text(text)
            current_hash = calculate_hash(cleaned_text)
            
            last_hash = previous_hashes.get(url)
            
            if last_hash is None:
                row["Resultado"] = "Nuevo (Primer Rastreo)"
                new_hashes[url] = current_hash
            elif current_hash != last_hash:
                row["Resultado"] = "🔴 CAMBIO DETECTADO"
                new_hashes[url] = current_hash
                changes_count += 1
            else:
                row["Resultado"] = "🟢 Sin Cambios"
        else:
            row["Resultado"] = "⚠️ Error de Lectura"
            errors_count += 1
            
        processed_data.append(row)
    
    # Save updated hashes
    save_hashes(new_hashes)
    st.session_state["last_results"] = processed_data
    
    status_placeholder.success(f"✅ Monitoreo completado. Cambios: {changes_count} | Errores: {errors_count}")
    # Clear progress bar after a moment (optional, leaving it for visibility now)


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
    df_no_changes = df[(df["Resultado"] == "🟢 Sin Cambios") & (df["Estado"] != "Error")]
    
    # 1. CHANGES (Highlighted)
    st.subheader(f"🚨 Sitios con Cambios ({len(df_changes)})")
    if not df_changes.empty:
        st.dataframe(
            df_changes.style.applymap(color_status, subset=['Resultado']),
            use_container_width=True,
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
            use_container_width=True,
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
                use_container_width=True,
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
