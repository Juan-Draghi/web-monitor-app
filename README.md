# Web Monitor App

Aplicacion de monitoreo de sitios web orientada a detectar cambios en paginas del mercado inmobiliario argentino. La interfaz esta hecha con Streamlit y el scraping combina `requests`, `BeautifulSoup` y casos especiales por dominio. El proyecto esta preparado para correr en Hugging Face Spaces como `Docker Space`.

## Estado actual

- La app monitorea las URLs definidas en `urls.txt`.
- El estado se persiste en un Hugging Face Dataset usando `web_monitoring_hashes.json`.
- Existe un recordatorio de revision manual cada 15 dias para sitios con falsos positivos recurrentes.
- La carpeta publica de Google Drive de la Universidad de San Andres ya esta integrada al monitoreo automatico.

## Desarrollo

Este proyecto fue desarrollado por Juan Draghi con asistencia de IA para programacion. La implementacion, refactorizacion y documentacion se trabajaron con ayuda de Codex / OpenAI, por lo que el repositorio no busca dar la impresion de ser un desarrollo hecho de forma completamente manual desde cero.

## Estrategias de monitoreo

La app no usa una unica tecnica para todos los sitios.

### 1. Sitios estaticos

Se procesan con `requests + BeautifulSoup`. Hoy este camino se usa en particular para dominios como:

- `afcp.org.ar`
- `uade.edu.ar`

### 2. Zonaprop

Las URLs de `zonaprop.com.ar/blog/zpindex/...` no se scrapean como pagina HTML. La app busca directamente el PDF mensual mas reciente publicado en `wp-content/uploads` y monitorea esa URL.

### 3. Google Drive publico

La carpeta publica de Google Drive de la Universidad de San Andres se monitorea como caso especial. La app extrae del HTML de la carpeta:

- nombre de archivo
- fecha modificada visible

La deteccion de cambios se basa en una firma estable de las publicaciones mas recientes.

### 4. Sitios dinamicos o problemáticos

El resto de las URLs puede pasar por Playwright cuando hace falta, aunque el proyecto esta en proceso de redisenio para reducir ese uso al minimo posible.

## Sitios excluidos del monitoreo automatico

Estos sitios daban falsos positivos frecuentes con Playwright y quedaron fuera del scraping automatico. Se revisan manualmente cada 15 dias desde la propia app:

- `https://adrianmercadorealestate.com/blog/informes`
- `https://www.colliers.com/es-ar`
- `https://www.fabianachaval.com/blog`
- `https://www.ljramos.com.ar/informes-del-mercado-inmobiliario`
- `https://www.cbre.com.ar/insights#market-reports`

La fecha de esa revision manual se guarda en `manual_review_schedule.json`.

## Persistencia

La app usa el mismo `DATASET_ID` para guardar dos archivos JSON:

- `web_monitoring_hashes.json`
  Guarda el ultimo hash conocido por URL.
- `manual_review_schedule.json`
  Guarda la ultima fecha de revision manual de los sitios excluidos.

No hace falta configurar datasets separados.

## Configuracion en Hugging Face Spaces

Configurar estos secrets:

- `HF_TOKEN`
- `DATASET_ID`

Sin esos secrets la app igual funciona, pero el estado no persiste entre reinicios.

## Variables de entorno opcionales

- `BATCH_SIZE`
- `MAX_RETRIES`
- `REQUEST_TIMEOUT`
- `PAGE_GOTO_TIMEOUT_MS`
- `PAGE_IDLE_TIMEOUT_MS`
- `PAGE_TEXT_TIMEOUT_MS`

Valores conservadores recomendados para Hugging Face Spaces:

```text
BATCH_SIZE=1
MAX_RETRIES=2
REQUEST_TIMEOUT=30
PAGE_GOTO_TIMEOUT_MS=45000
PAGE_IDLE_TIMEOUT_MS=3000
PAGE_TEXT_TIMEOUT_MS=5000
```

## Estructura del proyecto

```text
web-monitor-app/
|-- app.py
|-- urls.txt
|-- Dockerfile
|-- requirements.txt
|-- packages.txt
|-- redesign/
`-- README.md
```

## Redisenio en curso

El proyecto tiene un replanteo documentado en:

- `redesign/README.md`
- `redesign/url_strategy_matrix.csv`

La direccion propuesta es pasar de "Playwright para casi todo" a una estrategia por tipo de sitio:

- `requests` primero
- parseo estructurado de listados
- casos especiales por dominio
- Playwright solo donde sea realmente necesario

## Ejecucion local

Instalar dependencias:

```powershell
python -m pip install -r requirements.txt
```

Ejecutar Streamlit:

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 7860
```

## Limitaciones conocidas

- Hugging Face Spaces free puede resultar inestable para scraping pesado con Playwright.
- Algunos sitios cambian protecciones anti-bot y pueden requerir ajustes de estrategia.
- El siguiente paso arquitectonico probable es separar scraping y dashboard.

## Archivos relevantes

- `urls.txt`: lista definitiva de URLs monitoreadas
- `redesign/`: base documental del redisenio de estrategia
