# 0002 - Registrar URLs exitosas sin cambios para revision manual

## Estado

Aceptado

## Fecha

2026-07-15

## Contexto

El monitoreo por hash detecta cambios en el contenido de una URL. Sin embargo,
algunos sitios pueden modificar su estructura y mover informes o novedades a
otra direccion. En ese caso, la URL monitoreada puede seguir respondiendo sin
errores y sin cambios relevantes, aunque el contenido de interes ya no este
alli.

La persona usuaria propuso una revision mensual de URLs sin cambios en los
ultimos 30 dias.

## Decision

Agregar metadatos por URL y una seccion **Revisar manualmente** en la interfaz.

La aplicacion guarda `web_monitoring_metadata.json` con:

- primera vez vista;
- ultima lectura exitosa;
- ultimo cambio detectado;
- ultimo estado;
- ultimo error;
- corridas consecutivas sin cambios;
- corridas consecutivas con error.

Una URL aparece en **Revisar manualmente** cuando:

- sigue presente en `urls.txt`;
- fue leida correctamente;
- no tuvo cambios detectados durante 30 dias o mas.

## Alternativas consideradas

- **Revision manual completa mensual:** simple, pero depende de memoria y exige
  revisar todas las URLs.
- **Rastreo automatico de sitios completos:** podria encontrar contenido movido,
  pero aumenta ruido, costo de mantenimiento y riesgo de falsos positivos.
- **Lista automatica de URLs sin cambios:** mantiene el flujo simple y enfoca la
  revision humana donde hay mayor riesgo operativo.

## Consecuencias

- El conteo empieza desde la primera corrida posterior a la implementacion.
- `web_monitoring_metadata.json` es un archivo local generado y no se versiona.
- La app no decide si el sitio cambio de estructura; solo prioriza URLs que
  conviene revisar manualmente.
- El umbral queda definido en `STALE_REVIEW_DAYS = 30`.

## Verificacion

- Validacion de sintaxis Python con `ast`.
- Simulacion de una URL con 31 dias sin cambios.
- Verificacion de endpoints Flask `/` y `/results`.
- Recompilacion de `MonitoreoWeb.exe`.
