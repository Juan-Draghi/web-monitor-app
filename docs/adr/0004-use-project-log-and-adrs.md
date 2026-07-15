# 0004 - Usar project log y ADRs para trazabilidad

## Estado

Aceptado

## Fecha

2026-07-15

## Contexto

La fase de implementacion incluyo cambios funcionales, correcciones de flujo y
decisiones metodologicas. Para que el proyecto sea mantenible por personal no
desarrollador, hace falta registrar no solo que cambio, sino tambien por que se
cambio y como se verifico.

## Decision

Mantener dos niveles de documentacion:

- `docs/project-log.md`: registro cronologico de cambios relevantes, problemas,
  motivos y verificaciones.
- `docs/adr/`: decisiones tecnicas o metodologicas con contexto, alternativas y
  consecuencias.

`AGENTS.md` indica que, antes de commitear, se debe revisar si el cambio
requiere entrada en el log o ADR.

## Alternativas consideradas

- **Solo commits:** registran cambios, pero no siempre explican contexto,
  alternativas ni consecuencias.
- **Solo README:** util para documentacion vigente, pero no como historia de
  decisiones.
- **Log + ADRs:** separa cronologia operativa de decisiones con impacto futuro.

## Consecuencias

- Los cambios relevantes deben dejar trazabilidad documental.
- Las decisiones no se borran ni reescriben silenciosamente; si cambian, se crea
  un nuevo ADR.
- La documentacion agrega una tarea breve al cierre de cada cambio, pero reduce
  perdida de contexto en futuras sesiones.

## Verificacion

- Se creo `docs/project-log.md`.
- Se creo `docs/adr/README.md`.
- Se crearon ADRs iniciales para las decisiones tomadas en la fase de
  implementacion.
- Se actualizo `AGENTS.md` con la regla de mantenimiento futuro.
