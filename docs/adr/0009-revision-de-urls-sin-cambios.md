# 0009 - Revisión y clasificación de URLs sin cambios

## Estado

Aceptado. Complementa el ADR 0002.

## Fecha

2026-11-15

## Contexto

El ADR 0002 incorporó la sección **Revisión por antigüedad** para URLs leídas
correctamente sin cambios detectados durante 30 días o más. Esas URLs
permanecían en la lista en cada corrida y se acumulaban con las nuevas, sin
forma de distinguir las revisadas de las pendientes ni de organizar el
seguimiento según el resultado de la revisión. Al 15/11/2026 había 8 URLs en
esa sección, tres con 112 días sin cambios.

«Sin cambios detectados» no implica que el sitio esté inactivo: puede no haber
novedades o la aplicación puede estar dejando de detectarlas.

## Decisión

- **Archivo propio `revisiones_urls.json`**, escrito sólo por las acciones de
  revisión. Las corridas lo leen al final, de modo que una revisión hecha
  durante una corrida no se pierde (los metadatos se leen al inicio y se
  reescriben al final de cada corrida). Es un dato local y no se versiona.
- **Sin novedades (R1):** la URL sale de la lista en el momento y el plazo de
  30 días cuenta desde la fecha más reciente entre la revisión y el último
  cambio detectado. El aviso vuelve en una corrida que evalúe la URL al
  cumplirse el plazo.
- **Cambios no detectados (R2):** la URL pasa a **URLs a revisar**, con nota
  opcional.
- **Sitio inactivo o caído (R3):** una sola categoría, **Sitios inactivos o
  caídos**, con nota opcional y datos de apoyo (última lectura exitosa y último
  cambio). Se usó ese nombre en lugar de «URLs con error» para no confundirla
  con **No verificadas**, donde ya aparecen los sitios que no responden.
- En ambas secciones la URL se sigue monitoreando y no vuelve a la revisión
  por antigüedad. Se cierra sólo de forma manual con **Marcar como resuelta**;
  desde ese día vuelve a contar el plazo.
- Las revisiones no se registran en `historial_fuentes.md` (el ADR 0008 excluye
  las revisiones que no modifican la fuente). Bajas y modificaciones derivadas
  se hacen desde el panel de fuentes, con motivo.
- Si la causa todavía no se conoce, la URL se deja pendiente sin clasificar.

## Alternativas consideradas

- **Guardar la revisión en `web_monitoring_metadata.json`:** evita un archivo
  nuevo, pero una revisión hecha durante una corrida se perdería al terminar.
- **Cerrar «URLs a revisar» automáticamente al detectarse un cambio:** un
  cambio cualquiera (menú, fecha) no prueba que se detecten las novedades
  relevantes.
- **Dos categorías para R3 (caída temporal y abandono confirmado):** más
  precisa, pero requiere reglas propias para cada una; la nota opcional cubre
  la distinción.
- **Nota obligatoria:** la sección elegida ya indica la causa.

## Consecuencias

- Las URLs revisadas desaparecen de la lista sin esperar a la corrida
  siguiente; los días mostrados corresponden a la última corrida.
- Una URL clasificada no vuelve a la revisión por antigüedad hasta resolverse,
  aunque pasen más de 30 días.
- Si `revisiones_urls.json` se daña, se ignora y el monitoreo continúa; las
  URLs vuelven a evaluarse según el criterio del ADR 0002.
- Un archivo local más que no se respalda en GitHub (queda en OneDrive).

## Verificación

- `tests/test_revisiones.py`: los ejemplos de la especificación con fechas
  simuladas (salida inmediata, nuevo plazo de 30 días, reaparición, reinicio
  por cambio detectado), clasificación con y sin nota, resolución,
  validaciones, fuente dada de baja, archivo dañado y revisión durante una
  corrida.
- Prueba en navegador sobre una copia de los datos reales (8 URLs pendientes):
  las tres acciones, «Marcar como resuelta», recarga y vista de 375 px.
