---
title: Web Monitor App
emoji: "🕵️"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
startup_duration_timeout: 1h
---

# Web Monitor App

Aplicacion de monitoreo de sitios web orientada a detectar cambios en paginas del mercado inmobiliario argentino. La interfaz esta hecha con Streamlit y el scraping combina `requests`, `BeautifulSoup` y `Playwright`, segun el tipo de sitio.

El proyecto esta preparado para correr en Hugging Face Spaces como `Docker Space`, y tambien puede ejecutarse en una PC local para pruebas.

## Que hace

- Lee las URLs desde `urls.txt`.
- Obtiene contenido usando la estrategia mas adecuada para cada sitio.
- Calcula hashes para detectar cambios entre ejecuciones.
- Guarda el estado en un Hugging Face Dataset cuando `HF_TOKEN` y `DATASET_ID` estan configurados.
- Muestra resultados agrupados en cambios detectados, errores y sitios sin cambios.

## Estrategias de scraping

### Zonaprop

Las URLs de `zonaprop.com.ar` no se monitorean con render completo. La app busca directamente el PDF mensual mas reciente publicado en `wp-content/uploads` y monitorea esa URL.

### AFCP

Las URLs de `afcp.org.ar` se consultan con `requests` y `BeautifulSoup`, evitando el costo de abrir un navegador.

### Resto de sitios

Las demas URLs se procesan con `Playwright` y Chromium headless.

## Optimizaciones aplicadas

Para mejorar la estabilidad en Hugging Face Spaces, la app usa un perfil de ejecucion conservador:

- Reutiliza una sola instancia de Chromium por corrida.
- Reutiliza una `requests.Session()` compartida para reducir overhead HTTP.
- Procesa pocas URLs en paralelo por defecto.
- Usa timeouts configurables por entorno.
- Evita APIs deprecadas de Streamlit en la UI.

Estas mejoras reducen consumo de memoria y CPU en `cpu-basic`.

## Estructura del proyecto

```text
web_monitor_app/
|-- app.py
|-- urls.txt
|-- Dockerfile
|-- requirements.txt
|-- packages.txt
`-- README.md
```

## Requisitos del Space

Este proyecto debe publicarse como `Docker Space`. Los archivos minimos que tienen que estar en el repo del Space son:

- `app.py`
- `Dockerfile`
- `requirements.txt`
- `packages.txt`
- `urls.txt`
- `README.md`

## Secrets y variables

### Secrets recomendados

- `HF_TOKEN`: token de Hugging Face con permisos para leer y escribir en el dataset.
- `DATASET_ID`: dataset donde se guardan los hashes, por ejemplo `usuario/web-monitor-hashes`.

Sin esos secretos la aplicacion igual funciona, pero el estado se pierde al reiniciar el Space.

### Variables de entorno opcionales

La app permite ajustar su agresividad sin cambiar codigo:

- `BATCH_SIZE`: cantidad de URLs procesadas por lote. Default: `1`.
- `MAX_RETRIES`: reintentos por URL cuando falla Playwright. Default: `2`.
- `REQUEST_TIMEOUT`: timeout en segundos para requests HTTP. Default: `30`.
- `PAGE_GOTO_TIMEOUT_MS`: timeout de navegacion de Playwright en milisegundos. Default: `45000`.
- `PAGE_IDLE_TIMEOUT_MS`: espera maxima de `networkidle` en milisegundos. Default: `3000`.
- `PAGE_TEXT_TIMEOUT_MS`: timeout general de acciones de Playwright en milisegundos. Default: `5000`.

Valores conservadores recomendados para Hugging Face Spaces:

```text
BATCH_SIZE=1
MAX_RETRIES=2
REQUEST_TIMEOUT=30
PAGE_GOTO_TIMEOUT_MS=45000
PAGE_IDLE_TIMEOUT_MS=3000
PAGE_TEXT_TIMEOUT_MS=5000
```

## Despliegue en Hugging Face Spaces

1. Crear un Space nuevo de tipo `Docker`.
2. Subir el contenido del repo.
3. Configurar los secrets `HF_TOKEN` y `DATASET_ID`.
4. Esperar el build.
5. Abrir la app y ejecutar `Ejecutar Monitoreo Ahora`.

Si un Space anterior queda trabado en `paused` o devuelve `503` al reiniciar, crear un Space nuevo con el mismo repo puede resolverlo. En este proyecto ya ocurrio ese caso y el nuevo Space funciono correctamente con el mismo codigo.

## Ejecucion local

### Instalar dependencias

```powershell
python -m pip install -r requirements.txt
```

### Ejecutar Streamlit

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 7860
```

## Docker

El contenedor usa la imagen oficial de Playwright alineada con la version instalada en Python:

- Base image: `mcr.microsoft.com/playwright/python:v1.58.0-jammy`
- Playwright Python package: `1.58.0`

El `Dockerfile` tambien valida sintaxis con:

```text
python -m py_compile app.py
```

## Troubleshooting

### El Space compila pero no arranca

- Revisar los runtime logs, no solo los build logs.
- Confirmar que el Space sea `Docker`.
- Confirmar que `README.md` tenga el bloque YAML de Spaces.

### El Space queda en `paused` y devuelve `503` al reiniciar

- Probar `Factory reboot`.
- Si no se recupera, crear un Space nuevo con el mismo repo.
- Volver a cargar los secrets `HF_TOKEN` y `DATASET_ID`.

### El monitoreo consume demasiados recursos

- Mantener `BATCH_SIZE=1`.
- No subir `MAX_RETRIES` salvo necesidad real.
- Bajar la cantidad de URLs monitoreadas si el hardware es muy limitado.

### Se pierden los hashes al reiniciar

- Verificar que `HF_TOKEN` y `DATASET_ID` esten configurados.
- Probar el panel de diagnostico de la app para validar acceso al dataset.

## Limitaciones

- En Hugging Face Spaces free el almacenamiento local no persiste.
- Algunos sitios pueden cambiar sus defensas anti-bot y requerir ajustes de timeout o estrategia.
- Playwright mejora la cobertura, pero aumenta el consumo frente a una solucion solo con `requests`.

## Repositorio

GitHub: [Juan-Draghi/web-monitor-app](https://github.com/Juan-Draghi/web-monitor-app)
