# Registro de cambios del proyecto

Este archivo registra cambios relevantes del proyecto, el problema que los
origino, la solucion aplicada y las verificaciones realizadas.

Para decisiones tecnicas con alternativas o consecuencias relevantes, crear
ademas un ADR en `docs/adr/`.

## 2026-07-15 - Unificar archivo activo de URLs

**Problema**

La interfaz web y el monitoreo podian leer o escribir archivos `urls.txt`
distintos. En modo ejecutable, la aplicacion compilada usaba la copia ubicada
en `dist/MonitoreoWeb`, mientras que la edicion manual se realizaba sobre el
`urls.txt` de la raiz del proyecto.

**Cambio aplicado**

- Se centralizo la resolucion de la carpeta de datos en `monitor.py`.
- Se agrego una funcion unica para guardar URLs.
- El endpoint `/urls` informa la ruta activa del archivo.
- La interfaz muestra la ruta activa en el panel de gestion de URLs.
- El README documenta que la referencia valida es el `urls.txt` de la raiz.

**Motivo**

Evitar que la persona usuaria modifique una lista distinta de la que usa el
monitoreo real.

**Verificacion**

- Prueba de lectura de `/urls`.
- Prueba controlada de guardado con archivo temporal.
- Simulacion de ruta del ejecutable compilado.
- Recompilacion de `MonitoreoWeb.exe`.

**ADR relacionado**

- `docs/adr/0001-use-project-root-for-runtime-data.md`

## 2026-07-15 - Revision manual de URLs sin cambios recientes

**Problema**

Algunos sitios cambian su estructura o mueven el contenido a otra URL. Si la
URL monitoreada sigue respondiendo pero no cambia, la app no genera alerta y el
problema puede pasar inadvertido durante mucho tiempo.

**Cambio aplicado**

- Se agrego `web_monitoring_metadata.json` como archivo local de metadatos.
- Se registran por URL la ultima lectura exitosa, el ultimo cambio detectado y
  corridas consecutivas sin cambios.
- Se agrego la seccion **Revisar manualmente** en la interfaz.
- Las URLs leidas correctamente y sin cambios durante 30 dias o mas aparecen en
  esa seccion.
- `web_monitoring_metadata.json` se excluyo de Git.
- El README documenta el criterio de revision.

**Motivo**

Transformar una revision manual basada en memoria en una lista automatica y
priorizada, sin incorporar rastreo complejo ni fuentes externas.

**Verificacion**

- Validacion de sintaxis Python con `ast`.
- Prueba de calculo de URL vencida con datos simulados.
- Comprobacion de endpoints Flask `/` y `/results`.
- `git diff --check`.
- Recompilacion de `MonitoreoWeb.exe`.

**ADR relacionado**

- `docs/adr/0002-track-stale-successful-urls.md`

## 2026-07-15 - Publicacion directa a main

**Problema**

El flujo con ramas auxiliares y pull requests agregaba pasos innecesarios para
este proyecto, donde la persona usuaria prefiere simplicidad operativa.

**Cambio aplicado**

- Se actualizo `AGENTS.md` para que, despues de cada cambio, se pregunte si se
  quiere publicar.
- Si la publicacion se confirma, el flujo normal pasa a ser commit y push
  directo a `main`.
- Las ramas auxiliares y pull requests quedan reservados para pedidos
  explicitos.

**Motivo**

Reducir friccion y mantener el repositorio remoto actualizado sin requerir
gestion manual de ramas.

**Verificacion**

- Push directo a `origin/main`.
- Limpieza de rama auxiliar local y remota.

**ADR relacionado**

- `docs/adr/0003-publish-directly-to-main.md`

## 2026-07-15 - Incorporacion de project log y ADRs

**Problema**

La fase de implementacion acumulo decisiones funcionales y metodologicas que
quedaban dispersas entre commits, README y conversacion. Eso dificultaba
reconstruir por que se habia tomado cada decision.

**Cambio aplicado**

- Se creo `docs/project-log.md` como registro cronologico de cambios relevantes.
- Se creo `docs/adr/` para decisiones tecnicas y metodologicas.
- Se agrego `docs/adr/README.md` con criterios para crear y mantener ADRs.
- Se documentaron cuatro ADRs iniciales.
- Se actualizo `README.md` para enlazar la documentacion del proyecto.
- Se actualizo `AGENTS.md` para exigir revisar log y ADRs antes de commitear.

**Motivo**

Preservar trazabilidad de cambios, motivos, alternativas y verificaciones para
futuras sesiones de mantenimiento.

**Verificacion**

- Revision del contenido de `docs/project-log.md`.
- Revision de ADRs iniciales en `docs/adr/`.
- `git diff --check`.

**ADR relacionado**

- `docs/adr/0004-use-project-log-and-adrs.md`