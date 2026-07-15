# 0001 - Usar la raiz del proyecto como carpeta de datos operativos

## Estado

Aceptado

## Fecha

2026-07-15

## Contexto

La aplicacion puede ejecutarse de dos maneras:

- modo desarrollo, desde la raiz del proyecto;
- modo ejecutable, desde `dist/MonitoreoWeb/MonitoreoWeb.exe`.

Se detecto que la interfaz web y el monitoreo no siempre operaban sobre el
mismo `urls.txt`. El ejecutable podia leer y escribir `dist/MonitoreoWeb/urls.txt`,
mientras que la persona usuaria editaba el `urls.txt` de la raiz del proyecto.

Esto provocaba dos sintomas:

- los cambios hechos desde la interfaz no aparecian en el archivo esperado;
- los cambios manuales en `urls.txt` no eran usados por el monitoreo.

## Decision

Centralizar la resolucion de rutas en `monitor.py` y priorizar la raiz del
proyecto como carpeta de datos cuando el ejecutable corre desde
`dist/MonitoreoWeb`.

La ruta activa de `urls.txt` se expone desde el endpoint `/urls` y se muestra en
la interfaz.

## Alternativas consideradas

- **Guardar datos junto al ejecutable:** simple para distribucion, pero genera
  copias de datos dificiles de identificar durante desarrollo y recompilacion.
- **Usar siempre la raiz del proyecto:** mas claro para este uso interno,
  porque la persona usuaria trabaja dentro de la carpeta del proyecto.
- **Pedir al usuario elegir archivo:** agrega complejidad innecesaria para una
  app de uso local.

## Consecuencias

- Hay un unico `urls.txt` operativo.
- La interfaz ayuda a verificar la ruta activa.
- Si se distribuyera el ejecutable fuera de la carpeta del proyecto, volveria a
  usar la carpeta del ejecutable como fallback.

## Verificacion

- Prueba de lectura del endpoint `/urls`.
- Prueba de escritura con archivo temporal.
- Simulacion de ruta PyInstaller.
- Recompilacion de `MonitoreoWeb.exe`.
