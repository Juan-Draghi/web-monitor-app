# 0006 - Controlar corridas prolongadas y cancelación

## Estado

Aceptado

## Fecha

2026-08-31

## Contexto

El monitoreo se ejecutaba en un hilo del servidor y sólo liberaba el estado
`running` cuando terminaba el procesamiento completo. Recargar la página no
detenía ese hilo y la interfaz no recuperaba el estado activo, por lo que un
nuevo intento respondía `Ya hay una corrida en curso`.

Aunque `requests` y varias operaciones de Playwright tenían tiempos parciales,
no existía un límite que englobara todo el procesamiento de una fuente. Una
operación dinámica podía quedar bloqueada indefinidamente y detener las fuentes
restantes. Tampoco existía un mecanismo de cancelación ni se informaba con
claridad qué páginas requerían verificación manual.

## Decisión

- Limitar el procesamiento completo de cada fuente a 120 segundos.
- Si una fuente agota el tiempo o produce un error inesperado, registrarla como
  no verificada y continuar con la siguiente.
- Incorporar cancelación cooperativa mediante `threading.Event` y el endpoint
  `POST /cancel`.
- Comprobar la señal de cancelación durante la lectura de la fuente activa y
  entre fuentes.
- Conservar los hashes, metadatos y resultados de la última corrida completa si
  una ejecución es cancelada.
- Recuperar el estado de una corrida activa al cargar o recargar la interfaz.
- Mostrar las fuentes fallidas en la sección **No verificadas**, con el motivo y
  un enlace para su consulta manual.
- Registrar las excepciones generales en lugar de descartarlas silenciosamente.

## Alternativas consideradas

- **Cerrar y volver a abrir la aplicación:** libera una corrida bloqueada, pero
  depende de una acción externa y no previene que el problema se repita.
- **Agregar sólo un botón de cancelación:** permite intervenir, pero una fuente
  bloqueada sigue requiriendo supervisión permanente.
- **Aplicar sólo un timeout:** evita bloqueos indefinidos, pero no permite
  detener una corrida que la persona usuaria ya no necesita.
- **Cancelar y aplicar timeout por fuente:** cubre tanto la intervención manual
  como la continuidad automática y mantiene el flujo simple.

## Consecuencias

- Una página problemática no detiene el resto del monitoreo.
- Las fuentes no verificadas requieren consulta manual y no actualizan su hash
  como si hubieran sido leídas correctamente.
- Una cancelación puede demorar brevemente mientras se cierran recursos de
  Playwright, pero la interfaz muestra el estado `Cancelando`.
- Los resultados parciales de una corrida cancelada no se publican; permanece
  visible la última ejecución completa.
- El estado de ejecución continúa siendo local al proceso. Reiniciar la
  aplicación elimina una marca de corrida activa, pero no los resultados
  operativos guardados.

## Verificación

- Pruebas de timeout con continuidad sobre la fuente siguiente.
- Prueba de cancelación durante una fuente activa.
- Prueba de excepción inesperada sin interrupción del lote.
- Prueba de no sobrescritura de resultados al cancelar.
- Pruebas de los endpoints `/run`, `/cancel` y `/status`.
- Verificación de recuperación de controles y listado de fuentes no verificadas
  en la interfaz.
- Recompilación y prueba del ejecutable.
