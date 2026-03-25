# Monitor web en Google Colab

Este repositorio contiene un cuaderno de Google Colab para monitorear sitios web vinculados al mercado inmobiliario y detectar publicaciones nuevas o cambios relevantes.

## Estructura del proyecto

- [colab/web_monitor_colab.ipynb](/G:/Mi%20unidad/Proyectos/web-monitor-app/colab/web_monitor_colab.ipynb): notebook principal.
- `urls.txt`: lista de URLs monitoreadas.
- `web_monitoring_hashes.json`: hashes de la última versión conocida de cada URL.
- `last_run_results.json`: resultados completos de la última ejecución.

En Colab, esos tres archivos se guardan en:

`/content/drive/MyDrive/Proyectos/web-monitor-app`

## Cómo funciona

El notebook:

1. monta Google Drive;
2. usa una carpeta persistente de trabajo;
3. crea `urls.txt` la primera vez, si todavía no existe;
4. monitorea automáticamente las URLs definidas;
5. guarda hashes para comparar cada ejecución con la anterior;
6. genera un archivo de resultados con el detalle de la corrida.

## Estrategia de monitoreo

- Usa `requests` + `BeautifulSoup` como método principal.
- Tiene estrategias especiales para Google Drive y Zonaprop.
- Deja 5 sitios fuera del monitoreo automático porque daban falsos positivos frecuentes y conviene revisarlos manualmente.
- Puede usar `Playwright + Chromium` como fallback opcional, pero no es el modo recomendado por defecto.

## Uso

1. Abrir [colab/web_monitor_colab.ipynb](/G:/Mi%20unidad/Proyectos/web-monitor-app/colab/web_monitor_colab.ipynb) en Google Colab.
2. Ejecutar las celdas en orden.
3. Dejar `USAR_PLAYWRIGHT_FALLBACK = False`, salvo que haga falta para una URL puntual.
4. Revisar el resumen final en la última celda.
5. Si hace falta más detalle, abrir `last_run_results.json` en la carpeta de Google Drive.

## Salida esperada

Al finalizar una corrida, el notebook informa:

- cantidad de URLs automáticas procesadas;
- cambios detectados;
- errores de lectura;
- sitios reservados para revisión manual.

Los resultados detallados quedan guardados en `last_run_results.json`.

## Nota sobre autoría

Este proyecto fue desarrollado por Juan Draghi con asistencia de OpenAI Codex para el diseño, la refactorización y la documentación técnica. El criterio de monitoreo, la selección de fuentes y la validación de resultados responden al uso real del proyecto.
