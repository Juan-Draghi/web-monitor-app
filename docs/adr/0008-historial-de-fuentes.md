# 0008 - Historial de fuentes con motivo obligatorio

## Estado

Aceptado

## Fecha

2026-11-15

## Contexto

Las altas, bajas y modificaciones de fuentes no dejaban registro del cambio ni
de su causa, por lo que no se podía reconstruir qué se modificó y por qué. La
interfaz guardaba la lista completa de una vez, sin distinguir operaciones, y
`urls.txt` también se editaba a mano o desde GitHub.

## Decisión

- **Operaciones de a una.** Se eliminó el guardado de la lista completa
  (`POST /urls`). Cada alta, baja o modificación tiene su endpoint
  (`/urls/add`, `/urls/remove`, `/urls/update`) y exige motivo; sin motivo no
  se modifica ningún archivo.
- **Archivo `historial_fuentes.md`** en la raíz del proyecto, en Markdown: un
  bloque por cambio con fecha, acción, URL, URL anterior (modificaciones),
  motivo y, en bajas, si continúa el seguimiento manual fuera de la
  aplicación. El motivo se guarda en una sola línea para mantener una
  estructura estable.
- **Inventario inicial.** La primera vez que se abre la aplicación se crea el
  historial con las fuentes vigentes en `urls.txt`.
- **Coherencia entre archivos.** Se preparan borradores de `urls.txt` y del
  historial; se reemplaza `urls.txt` y luego el historial. Si falla el
  historial, se restaura el `urls.txt` anterior y se informa que el cambio no
  se aplicó.
- **Cambios externos.** Al abrir la página se reconstruye la lista esperada
  aplicando en orden los registros del historial y se compara con `urls.txt`.
  Las diferencias se muestran como fuentes agregadas o quitadas y se registran
  con motivo como «Alta/Baja (fuera de la aplicación)». Registrar no modifica
  `urls.txt` ni bloquea el monitoreo.
- **Publicación.** El historial se versiona y publica en GitHub junto con
  `urls.txt` (repositorio público). La interfaz advierte que los motivos deben
  describir hechos verificables.

## Alternativas consideradas

- **Mantener la edición en lote y pedir motivos al guardar:** no permite
  distinguir con seguridad una modificación de una baja más un alta.
- **CSV en lugar de Markdown:** se filtra en Excel, pero se lee peor sin
  herramientas y los motivos con comas o saltos complican el formato.
- **Ignorar los cambios hechos fuera de la aplicación:** más simple, pero deja
  sin registro una vía de modificación que se usa en la práctica.
- **Historial solo local (fuera de git):** mantiene privados los motivos, pero
  lo separa de la historia del proyecto; se priorizó publicarlo.

## Consecuencias

- Ya no se pueden reordenar fuentes ni hacer varios cambios con un solo
  guardado.
- Una URL cambiada a mano se detecta como una baja más un alta.
- Si el historial se edita a mano y queda un registro irreconocible, la
  comparación informa el error en lugar de ocultarlo.
- Cada cambio de fuentes genera cambios pendientes de publicar en
  `historial_fuentes.md` y `urls.txt`.
- Queda un riesgo mínimo ante un corte de energía entre los dos reemplazos;
  la comparación de cambios externos lo pondría en evidencia al abrir la app.

## Verificación

- `tests/test_fuentes.py`: motivo obligatorio en cada operación, registro de
  alta, baja y modificación, seguimiento manual, conservación de registros
  sucesivos, validaciones, bloqueo durante corridas, fallos de guardado con
  restauración, detección y registro de cambios externos, lista desactualizada
  e historial irreconocible. La conservación se comprueba comparando contenido.
- Prueba en navegador sobre una copia con datos de prueba (escritorio y
  pantalla de 375 px).
