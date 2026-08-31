# Selección Informativa — Monitoreo web

Aplicación de escritorio para Windows que monitorea sitios web vinculados al mercado inmobiliario y detecta publicaciones nuevas o cambios de contenido. Desarrollada para uso interno del **Consejo Profesional de Arquitectura y Urbanismo (CPAU)**.

## Requisitos

- Windows 10 o superior
- Python 3.10 o superior ([python.org](https://www.python.org/downloads/))
- Conexión a internet (para la primera instalación y cada corrida)

## Instalación

Ejecutar **una sola vez**:

```
instalar.bat
```

Esto crea un entorno virtual, instala todas las dependencias (Flask, Playwright, BeautifulSoup, requests) y descarga el navegador Chromium necesario para los sitios con contenido dinámico.

## Uso diario

### Opción A — Ejecutable compilado (recomendada)

Compilar el ejecutable **una sola vez** tras la instalación:

```
compilar.bat
```

Al finalizar, crea un acceso directo en el escritorio. El doble clic abre la interfaz en el navegador automáticamente.

### Opción B — Modo desarrollo

```
ejecutar.bat
```

Inicia el servidor Flask directamente desde el entorno virtual. Útil para modificar el código.

## Interfaz

La aplicación corre en `http://localhost:5000` y utiliza una interfaz operativa neutra, sin fuentes ni recursos visuales externos. La pantalla organiza el trabajo en cuatro niveles:

- **Ejecución**: fecha de la última corrida, estado del navegador dinámico, botón principal y progreso.
- **Resumen**: total de fuentes, cambios, altas iniciales, revisiones manuales y errores.
- **Resultados**: cambios detectados como contenido prioritario y estados secundarios plegables.
- **Fuentes monitoreadas**: panel cerrado por defecto para agregar, editar, eliminar y guardar URLs.

El diseño se adapta a pantallas de escritorio, tablet y móvil sin desplazamiento horizontal.

## Archivos principales

| Archivo | Descripción |
|---|---|
| `urls.txt` | Lista de URLs monitoreadas (una por línea) |
| `monitor.py` | Lógica de monitoreo, hashing y detección de cambios |
| `app.py` | Servidor Flask y manejo de estado |
| `templates/index.html` | Estructura y comportamiento de la interfaz web |
| `static/operational-ui.css` | Sistema visual neutro y reglas responsive |
| `monitoreo.spec` | Configuración de compilación PyInstaller |
| `instalar.bat` | Instalación de dependencias |
| `compilar.bat` | Generación del ejecutable `.exe` |
| `ejecutar.bat` | Inicio en modo desarrollo |

## Documentación del proyecto

- `docs/project-log.md`: registro cronológico de cambios relevantes, motivos y verificaciones.
- `docs/adr/`: decisiones técnicas o metodológicas con contexto, alternativas y consecuencias.

## Archivo activo de URLs

La lista que usa el monitoreo es `urls.txt` en la carpeta raíz del proyecto.
La interfaz web también escribe sobre ese mismo archivo y muestra la ruta activa
en el panel **Gestionar lista de URLs**.

Si se recompila el ejecutable, no editar copias antiguas de `urls.txt` dentro
de `dist/MonitoreoWeb`; la referencia válida es la ruta indicada por la
interfaz.

## Revisión manual por antigüedad

La aplicación guarda metadatos operativos en `web_monitoring_metadata.json`.
Ese archivo registra, por URL, la última lectura exitosa, el último cambio
detectado y la cantidad de corridas consecutivas sin cambios.

Si una URL fue leída correctamente pero no tuvo cambios detectados durante 30
días o más, aparece en la sección **Revisión por antigüedad** de la interfaz.
Esto permite detectar sitios que movieron su contenido aunque la URL original
siga respondiendo sin novedades.

## Cancelación y fuentes no verificadas

Cada fuente dispone de un máximo de 120 segundos para completar su lectura. Si
ese tiempo se agota o se produce un error inesperado, la aplicación registra la
página como **No verificada**, continúa con la fuente siguiente y ofrece un
enlace para revisarla manualmente.

Mientras hay una corrida activa, la interfaz muestra el botón **Cancelar
corrida**. La cancelación puede tardar unos segundos mientras se cierra el
navegador de la fuente actual. Una corrida cancelada no reemplaza los hashes,
metadatos ni resultados de la última ejecución completa.

Si se recarga la página durante una corrida, la interfaz consulta el estado del
servidor y recupera automáticamente el progreso y el control de cancelación.
Recargar el navegador por sí solo no detiene el proceso.

Los errores y timeouts se muestran en **No verificadas** con su causa. Esas
páginas deben abrirse y consultarse manualmente cuando la información sea
necesaria.

## Estrategia de monitoreo

- **Método principal**: `requests` + `BeautifulSoup` para sitios estáticos
- **Playwright (Chromium)**: método primario para sitios con contenido dinámico (adrianmercadorealestate.com, fabianachaval.com, ljramos.com.ar, cbre.com.ar); fallback para el resto
- **Extractor de títulos**: para dominios dinámicos extrae solo títulos de artículos, descartando ads y widgets, para evitar falsos positivos
- **Zonaprop**: detecta el PDF del informe mensual directamente desde la página
- **Google Drive**: lista los archivos más recientes de carpetas compartidas

## Actualizar dependencias

Las dependencias están fijadas al entorno virtual. Para actualizar:

```
venv\Scripts\python -m pip install --upgrade requests beautifulsoup4 playwright flask
venv\Scripts\python -m playwright install chromium
```

Luego volver a compilar con `compilar.bat`.

---

*Desarrollado por Juan Draghi con asistencia de Claude (Anthropic) para la arquitectura, refactorización y documentación técnica.*
