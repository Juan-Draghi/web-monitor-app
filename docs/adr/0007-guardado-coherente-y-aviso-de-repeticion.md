# 0007 - Guardado coherente de corridas y aviso de repetición

## Estado

Aceptado

## Fecha

2026-11-15

## Contexto

Repetir por accidente una corrida pocos minutos después de la anterior compara
las fuentes con un relevamiento muy reciente, suele devolver cero novedades y
reemplaza los resultados que todavía se necesitaban para preparar el
newsletter.

Además, al terminar una corrida se escribían tres archivos uno después de
otro: referencias de comparación (`web_monitoring_hashes.json`), metadatos
(`web_monitoring_metadata.json`) y resultados (`last_run_results.json`). Si el
proceso fallaba entre esas escrituras, las referencias podían quedar
actualizadas sin que los resultados reflejaran las novedades detectadas: la
corrida siguiente las informaba como «Sin cambios» y se perdían. Un archivo
escrito a medias tampoco podía leerse después. Este riesgo surgió de la lectura
del código; no se reprodujo en uso real.

La cancelación y los fallos durante el recorrido ya conservaban los datos de
la última corrida completa (ADR 0006).

## Decisión

- **Aviso de repetición.** Antes de iniciar una corrida, el servidor calcula el
  tiempo transcurrido desde que se guardó la última corrida completada
  (`generated_at` de `last_run_results.json`). Si es menor de 60 minutos,
  `POST /run` no inicia nada y responde `409` con `confirmation_required`; la
  interfaz muestra el aviso con las opciones «No ejecutar» y «Ejecutar igual».
  Solo `{"confirm_repeat": true}` inicia la corrida. A los 60 minutos exactos
  no hay aviso. Las corridas canceladas o fallidas no guardan resultados, por
  lo que no reinician el plazo.
- **Guardado en dos pasos.** Primero se escriben los tres archivos como
  borradores `.tmp` (forzados al disco); si alguno falla, se descartan y no se
  toca ningún archivo real. Después se reemplaza cada archivo real por su
  borrador con `os.replace`, que es instantáneo y no deja archivos a medias.
- **Orden de reemplazo: resultados → metadatos → referencias.** Si el proceso
  se corta entre reemplazos, la corrida siguiente puede volver a mostrar una
  novedad ya detectada, pero no la pierde. Se prefirió una novedad repetida a
  una novedad perdida.
- Si Windows bloquea un archivo por un instante (OneDrive, antivirus), el
  reemplazo se reintenta hasta cinco veces.
- Una fuente con error conserva su última referencia válida; las fuentes
  leídas correctamente la actualizan al completarse la corrida (comportamiento
  previo, ahora cubierto por pruebas).

## Alternativas consideradas

- **Aviso solo en la página:** más simple, pero no protege si hay dos pestañas
  abiertas y no se puede probar automáticamente.
- **Ventana `confirm()` del navegador:** inmediata, pero fuera del estilo de la
  interfaz y sin texto claro sobre qué se conserva.
- **Unificar los tres archivos en uno:** haría el guardado completamente
  atómico, pero cambia el formato de datos existente y su lectura; desproporcionado
  para el riesgo.
- **Copias de respaldo de cada archivo antes de guardar:** agrega archivos y
  un procedimiento de recuperación manual sin evitar el estado inconsistente.
- **Orden de reemplazo con referencias primero (anterior):** ante un corte,
  pierde novedades sin aviso.

## Consecuencias

- Pedir una corrida antes de los 60 minutos requiere una confirmación
  adicional; también después de un intento fallido dentro del plazo.
- Un corte de energía en el instante exacto entre reemplazos puede repetir una
  novedad en la corrida siguiente.
- Pueden quedar archivos `*.tmp` solo si el proceso se corta durante el
  guardado; están excluidos de git y se sobrescriben en el guardado siguiente.
- Cada cambio de código requiere recompilar el ejecutable que abre el acceso
  directo del escritorio.

## Verificación

- `tests/test_save_outputs.py`: guardado normal, cero novedades, fuentes con
  error, cancelación, fallo al preparar borradores, corte entre reemplazos y
  archivo bloqueado. La conservación se comprueba comparando contenido exacto.
  La prueba del corte falla si se restablece el orden anterior.
- `tests/test_repeat_warning.py`: 59 min, 59 min 59 s, 60 min exactos,
  cálculo desde el fin de la corrida, sin corrida previa, archivo dañado,
  rechazo, confirmación e intento fallido.
- Prueba en navegador sobre una copia con datos de prueba (escritorio y
  pantalla de 375 px).
