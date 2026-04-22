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

La aplicación corre en `http://localhost:5000` y muestra:

- **Última corrida**: fecha/hora y estado de Playwright
- **Cambios detectados**: URLs cuyo contenido cambió desde la corrida anterior
- **Nuevas en primer rastreo**: URLs procesadas por primera vez
- **Errores de lectura**: URLs que no pudieron ser accedidas
- **Gestionar URLs**: panel para agregar, editar o eliminar URLs sin tocar archivos

## Archivos principales

| Archivo | Descripción |
|---|---|
| `urls.txt` | Lista de URLs monitoreadas (una por línea) |
| `monitor.py` | Lógica de monitoreo, hashing y detección de cambios |
| `app.py` | Servidor Flask y manejo de estado |
| `templates/index.html` | Interfaz web (diseño CPAU) |
| `monitoreo.spec` | Configuración de compilación PyInstaller |
| `instalar.bat` | Instalación de dependencias |
| `compilar.bat` | Generación del ejecutable `.exe` |
| `ejecutar.bat` | Inicio en modo desarrollo |

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
