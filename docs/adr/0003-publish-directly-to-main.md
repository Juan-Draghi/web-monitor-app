# 0003 - Publicar cambios directamente en main

## Estado

Aceptado

## Fecha

2026-07-15

## Contexto

Durante la implementacion se creo una rama auxiliar y un pull request. La
persona usuaria indico que, para este proyecto, prefiere evitar ramas y PRs
como flujo normal y publicar directamente en `main`.

El proyecto es de uso interno y la prioridad operativa es reducir pasos
manuales innecesarios, manteniendo igualmente revision previa de diff y pruebas
razonables.

## Decision

Actualizar `AGENTS.md` para que el flujo normal sea:

1. implementar el cambio;
2. verificarlo;
3. preguntar explicitamente si se publica;
4. si la persona usuaria confirma, crear commit;
5. hacer push directo a `origin/main`.

No se crean ramas auxiliares ni pull requests salvo pedido explicito.

## Alternativas consideradas

- **Rama + pull request:** mejora trazabilidad formal, pero agrega friccion para
  un flujo individual y operativo.
- **Push directo a main:** reduce pasos y mantiene el repositorio remoto al dia.
- **Publicar sin preguntar:** descartado; se mantiene confirmacion explicita
  antes de hacer push.

## Consecuencias

- Los cambios quedan disponibles en `main` inmediatamente despues del push.
- La trazabilidad se apoya en commits claros, `docs/project-log.md` y ADRs.
- Si una modificacion futura requiere revision separada, la persona usuaria
  puede pedir rama o PR explicitamente.

## Verificacion

- Se actualizo `AGENTS.md`.
- Se hizo push directo a `origin/main`.
- Se elimino la rama auxiliar local y remota usada durante la implementacion.
