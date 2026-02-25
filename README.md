# 🕵️ Web Monitor App

Aplicación de monitoreo automático de sitios web desplegada en [Hugging Face Spaces](https://huggingface.co/spaces). Detecta cambios en el contenido de páginas de interés del mercado inmobiliario argentino y notifica visualmente cuando algo nuevo aparece.

## ¿Qué hace?

- **Monitorea una lista de URLs** definida en `urls.txt`
- **Detecta cambios** comparando un hash del contenido actual con el de la última verificación
- **Persiste el estado** entre ejecuciones usando un Hugging Face Dataset privado
- **Muestra los resultados** en una interfaz web construida con Streamlit, agrupados en: cambios detectados, errores y sitios sin cambios

## Estrategias de scraping

La app adapta su método de extracción según el tipo de sitio:

### 1. Zonaprop (`zonaprop.com.ar`)
Las páginas del blog de Zonaprop están protegidas por Cloudflare, por lo que se usa un enfoque alternativo: se hacen **HEAD requests directos** a los PDFs mensuales publicados en `wp-content/uploads`, que no tienen esa restricción. El monitor prueba automáticamente combinaciones de mes/año para encontrar el informe más reciente. El contenido monitoreado es la URL del PDF; cuando Zonaprop publica un nuevo informe mensual, la URL cambia y se detecta como cambio.

### 2. AFCP (`afcp.org.ar`)
Este sitio funciona con contenido estático. Se usa `requests` + `BeautifulSoup` para obtener el texto de la página, evitando la sobrecarga de un browser completo.

### 3. Resto de sitios
Se usa **Playwright** (browser headless Chromium) para renderizar páginas con contenido dinámico generado por JavaScript.

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| UI | [Streamlit](https://streamlit.io/) |
| Scraping dinámico | [Playwright](https://playwright.dev/python/) |
| Scraping estático | [requests](https://requests.readthedocs.io/) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) |
| Persistencia | [Hugging Face Datasets](https://huggingface.co/docs/datasets/) |
| Deploy | [Hugging Face Spaces](https://huggingface.co/spaces) (Docker SDK) |

## Estructura del proyecto

```
web_monitor_app/
├── app.py              # Aplicación principal
├── urls.txt            # Lista de URLs a monitorear (una por línea)
├── Dockerfile          # Configuración del entorno Docker para HF Spaces
├── requirements.txt    # Dependencias de Python
├── packages.txt        # Dependencias del sistema (para Playwright)
└── README.md
```

## Configuración (Secrets)

Para que el estado persista entre reinicios, configurar los siguientes secretos en Hugging Face Spaces:

| Secret | Descripción |
|---|---|
| `HF_TOKEN` | Token de Hugging Face con permisos de escritura |
| `DATASET_ID` | ID del dataset donde se guardan los hashes (ej. `usuario/web-monitor-hashes`) |

Sin estos secretos la app funciona igual, pero los hashes se pierden al reiniciar el Space.

## Uso

1. Acceder al Space en Hugging Face
2. Presionar **"Ejecutar Monitoreo Ahora"** en el sidebar
3. Esperar a que se procesen todas las URLs
4. Revisar los resultados:
   - 🔴 **CAMBIO DETECTADO** — el contenido del sitio cambió desde la última verificación
   - 🟢 **Sin Cambios** — sin novedades
   - ⚠️ **Error de Lectura** — no se pudo acceder al sitio

## Agregar o quitar URLs

Editar el archivo `urls.txt`: una URL por línea. Las URLs de Zonaprop (`zonaprop.com.ar/blog/zpindex/...`) tienen soporte especial para detección de PDFs mensuales.

---

## Créditos

Desarrollado con la asistencia de [Antigravity](https://antigravity.dev/), un agente de IA para programación de Google DeepMind.
