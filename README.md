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
| `historial_fuentes.md` | Historial de altas, bajas y modificaciones de fuentes, con motivo |
| `monitor.py` | Lógica de monitoreo, hashing y detección de cambios |
| `fuentes.py` | Cambios de fuentes con motivo obligatorio e historial |
| `revisiones.py` | Revisión manual de URLs sin cambios y su clasificación |
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

## Historial de fuentes

Las fuentes se agregan, modifican o dan de baja **de a una** desde el panel
**Gestionar lista de URLs**, y cada operación exige un motivo. El cambio y su
motivo quedan en `historial_fuentes.md`, en la carpeta raíz del proyecto:

- se puede leer en cualquier editor o pedirle a un agente que lo consulte;
- se publica en GitHub junto con el proyecto, por lo que los motivos deben
  describir hechos verificables, sin valoraciones internas;
- en las bajas se indica si continúa el seguimiento manual fuera de la
  aplicación (no existe una lista interna de seguimiento);
- lo escribe la aplicación: no editarlo a mano.

La primera vez que se abre la aplicación, el historial se crea con un
**inventario inicial** de las fuentes vigentes. Si después se edita `urls.txt`
a mano o desde GitHub, al abrir la aplicación aparece el aviso **Cambios en
urls.txt hechos fuera de la aplicación**, que pide el motivo de cada fuente
agregada o quitada para registrarla. Ese aviso no bloquea el monitoreo. Ver
`docs/adr/0008-historial-de-fuentes.md`.

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
siga respondiendo sin novedades. El cálculo se hace al terminar cada corrida.

Cada URL de esa sección se revisa manualmente y se marca con uno de tres
resultados:

- **Sin novedades:** sale de la lista y el plazo de 30 días vuelve a contar
  desde la revisión. Si antes se detecta un cambio, el plazo cuenta desde ese
  cambio.
- **Cambios no detectados:** pasa a **URLs a revisar**, con una nota opcional.
- **Sitio inactivo o caído:** pasa a **Sitios inactivos o caídos**, con una
  nota opcional y la fecha de la última lectura exitosa y del último cambio.

En las dos últimas secciones la URL se sigue monitoreando y no vuelve a la
revisión por antigüedad hasta que se marca como **resuelta**; desde ese día el
plazo vuelve a contar. Si la revisión termina en una baja o una modificación de
la fuente, se hace desde **Gestionar lista de URLs**, con su motivo. Si todavía
no se conoce la causa, la URL se deja pendiente.

Las revisiones se guardan en `revisiones_urls.json` (dato local, no se publica
en GitHub). Las corridas sólo leen ese archivo, por lo que se puede revisar
también mientras corre el monitoreo. Ver
`docs/adr/0009-revision-de-urls-sin-cambios.md`.

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

## Aviso de repetición

Si se pide una nueva corrida cuando pasaron menos de 60 minutos desde que
terminó la última corrida completada, la aplicación muestra un aviso y espera
confirmación: **No ejecutar** deja todo como está; **Ejecutar igual** inicia la
corrida. Las corridas canceladas o fallidas no cuentan para ese plazo.

Los resultados de la última corrida completada se reemplazan solo cuando la
nueva termina y se guarda correctamente. Si el guardado se interrumpe, la
aplicación prioriza no perder novedades: en ese caso excepcional, la corrida
siguiente puede volver a mostrar una novedad ya informada. Ver
`docs/adr/0007-guardado-coherente-y-aviso-de-repeticion.md`.

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
