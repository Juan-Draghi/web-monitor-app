# Registro de cambios del proyecto

Este archivo registra cambios relevantes del proyecto, el problema que los
origino, la solucion aplicada y las verificaciones realizadas.

Para decisiones tecnicas con alternativas o consecuencias relevantes, crear
ademas un ADR en `docs/adr/`.

## 2026-11-16 - Estilo Biblioteca CPAU y resultados en una columna

**Problema**

La interfaz usaba un sistema visual neutro y los cuadros secundarios de
resultados quedaban en una columna lateral angosta, donde los botones de
revision no entraban en una fila.

**Cambio aplicado**

- `static/cpau-ui.css` reemplaza a `static/operational-ui.css` con la
  identidad Biblioteca CPAU (paleta, Roboto, estetica plana).
- Logo y favicon CPAU, barra superior y pie nuevos.
- Resultados en una sola columna, a todo el ancho, sin desplazamiento interno.
- `CLAUDE.md` y README actualizados.

**Motivo**

Pedido de la persona usuaria: identidad institucional y mas espacio para los
botones de los resultados.

**Verificacion**

- Prototipo con copia de datos reales aprobado antes de aplicarlo.
- Capturas a 1366 px y 390 px, sin desplazamiento horizontal ni errores de
  consola.
- Pruebas automaticas y verificacion del ejecutable recompilado.

**ADR relacionado**

- `docs/adr/0010-adoptar-estilo-cpau.md` (reemplaza al ADR 0005)

## 2026-11-16 - INDEC: comparar el enlace al informe PDF

**Problema**

La pagina de INDEC (`.../indec/web/Nivel3-Tema-3-3`) carga su contenido con
JavaScript. La lectura sin navegador solo obtenia menu y pie de pagina (mas de
80 caracteres, por lo que no se usaba Playwright como respaldo). Se comparaba
ese texto: un cambio de menu el 03/11 reinicio el plazo de 30 dias y el
informe del ISAC del 06/11 no se detecto. Ningun mecanismo lo advirtio.

**Cambio aplicado**

- Para paginas de INDEC se lee la direccion interna equivalente
  (`.../Nivel3/Tema/3/3`) y se compara el enlace "Ver Informe" al PDF.
- Si el enlace no aparece, la fuente queda como error (no verificada) en lugar
  de "Sin cambios".
- Los resultados incluyen el campo `Documento` con el enlace al PDF (INDEC y
  Zonaprop) y la interfaz muestra "Abrir informe PDF".

**Motivo**

Detectar informes nuevos, que es lo que interesa de esta fuente, sin depender
de cambios de menu o cifras de portada.

**Verificacion**

- Auditoria de solo lectura de las 39 fuentes (lectura de la app frente a la
  pagina completa en navegador): solo INDEC comparaba contenido no relevante.
- `tests/test_indec.py`: conversion de direccion, lectura del enlace, error
  si falta, ruido sin efecto e informe nuevo detectado.
- Lectura real: devuelve `isac_11_26F4E69BED3F.pdf` (HTTP 200, PDF).
- La primera corrida posterior mostrara INDEC como "Cambio detectado" una vez.

## 2026-11-15 - Correcciones de compilar.bat

**Problema**

`compilar.bat` cerraba a la fuerza todos los procesos `node.exe` de la
computadora, incluidos los de otras herramientas, y la limpieza de PyInstaller
(`--clean`) fallaba con "Acceso denegado" dentro de la carpeta sincronizada por
OneDrive.

**Cambio aplicado**

- Solo se cierra el `node.exe` ubicado dentro de `dist\MonitoreoWeb`
  (el que usa Playwright).
- La carpeta de trabajo de PyInstaller pasa a `%TEMP%\monitoreo-pyi-build`.

**Verificacion**

- Ejecucion completa de `compilar.bat`: compilacion exitosa; los otros
  `node.exe` en ejecucion (2) siguieron activos.
- El ejecutable generado arranca y sirve la interfaz.
- No se probo el cierre de un `node.exe` de la app en ejecucion.

## 2026-11-15 - Revision y clasificacion de URLs sin cambios

**Problema**

Las URLs sin cambios durante 30 dias permanecian en **Revision por
antiguedad** en cada corrida y se acumulaban, sin distinguir las revisadas de
las pendientes ni organizar su seguimiento.

**Cambio aplicado**

- Se creo `revisiones.py` y el archivo local `revisiones_urls.json`.
- Tres resultados por URL: sin novedades (el plazo vuelve a contar desde la
  revision), cambios no detectados y sitio inactivo o caido (nota opcional).
- Secciones **URLs a revisar** y **Sitios inactivos o caidos**, con
  **Marcar como resuelta**.
- El calculo de 30 dias considera la ultima revision y excluye las URLs
  clasificadas; las revisiones se aplican en pantalla sin esperar otra corrida.
- `.gitignore` excluye `revisiones_urls.json`.

**Motivo**

Retirar de pendientes las URLs revisadas y organizar el seguimiento segun la
causa indicada, sin perder revisiones hechas durante una corrida.

**Verificacion**

- `venv\Scripts\python -m unittest discover tests`: 64 pruebas OK (13 nuevas).
- Prueba en navegador sobre una copia de los datos reales: las tres acciones,
  resolucion, recarga y vista movil. No se pudieron tomar capturas de
  escritorio (ventana oculta); la disposicion se verifico con mediciones.
- Recompilacion del ejecutable y comprobacion de que sirve la interfaz nueva
  sin modificar los datos.

**ADR relacionado**

- `docs/adr/0009-revision-de-urls-sin-cambios.md`

## 2026-11-15 - Historial de fuentes con motivo obligatorio

**Problema**

Las altas, bajas y modificaciones de fuentes no dejaban registro del cambio ni
de su causa. La interfaz guardaba la lista completa y `urls.txt` tambien se
editaba a mano o desde GitHub.

**Cambio aplicado**

- Se creo `fuentes.py` y el archivo `historial_fuentes.md`, con inventario
  inicial de las fuentes vigentes.
- Alta, baja y modificacion de a una, con motivo obligatorio; en las bajas se
  registra si continua el seguimiento manual fuera de la aplicacion.
- Se elimino el guardado de la lista completa (`POST /urls`).
- Guardado coherente de `urls.txt` e historial, con restauracion ante fallos.
- Deteccion de cambios hechos fuera de la aplicacion y registro de sus motivos.
- Nuevo panel de fuentes y aviso de cambios externos en la interfaz.

**Motivo**

Poder reconstruir que fuentes se agregaron, modificaron o dieron de baja y por
que, incluidas las decisiones derivadas de problemas de lectura.

**Verificacion**

- `venv\Scripts\python -m unittest discover tests`: 51 pruebas OK (24 nuevas).
- Prueba en navegador sobre una copia con datos de prueba: alta, baja con
  seguimiento manual, modificacion, rechazo sin motivo y por URL repetida,
  aviso y registro de cambios externos, vista movil.
- Recompilacion del ejecutable y comprobacion de que crea el inventario
  inicial y sirve la interfaz nueva.

**ADR relacionado**

- `docs/adr/0008-historial-de-fuentes.md`

## 2026-11-15 - Aviso de repeticion y guardado coherente de corridas

**Problema**

Una repeticion accidental de la corrida pocos minutos despues de la anterior
podia devolver cero novedades y reemplazar los resultados que se necesitaban
para el newsletter. Ademas, si el guardado final fallaba entre la escritura de
referencias, metadatos y resultados, las novedades detectadas podian perderse.

**Cambio aplicado**

- `POST /run` pide confirmacion si la ultima corrida completada termino hace
  menos de 60 minutos; la interfaz muestra el aviso con "No ejecutar" y
  "Ejecutar igual".
- El guardado de una corrida completada escribe primero borradores `.tmp` y
  luego reemplaza los archivos reales en el orden resultados, metadatos,
  referencias.
- Reintento breve si Windows bloquea un archivo al reemplazarlo.
- `.gitignore` excluye `*.tmp`.

**Motivo**

Conservar los resultados de la ultima corrida completada hasta que una nueva
termine y se guarde, y priorizar una novedad repetida antes que una perdida.

**Verificacion**

- `venv\Scripts\python -m unittest discover tests`: 27 pruebas OK (19 nuevas y
  2 existentes ajustadas para esta mejora).
- Prueba en navegador sobre una copia con datos de prueba: aviso, rechazo,
  confirmacion, conservacion de resultados durante la corrida y vista movil.
- Recompilacion del ejecutable y comprobacion de que sirve la interfaz nueva.

**ADR relacionado**

- `docs/adr/0007-guardado-coherente-y-aviso-de-repeticion.md`

## 2026-08-31 - Controlar corridas prolongadas y permitir cancelarlas

**Problema**

Una fuente podia dejar la corrida bloqueada indefinidamente. Recargar la pagina
no detenia el proceso y un nuevo intento respondia que ya habia una corrida en
curso. Ademas, no existia una indicacion operativa clara de las fuentes que no
pudieron verificarse.

**Cambio aplicado**

- Se incorporo un limite de 120 segundos para el procesamiento completo de cada
  fuente.
- Los timeouts y errores inesperados se registran como fuentes no verificadas y
  el monitoreo continua con la fuente siguiente.
- Se agrego cancelacion cooperativa mediante `POST /cancel` y un boton visible
  durante la corrida.
- La interfaz recupera el estado activo despues de una recarga.
- Las fuentes fallidas se muestran en **No verificadas**, con el motivo y un
  enlace para revisarlas manualmente.
- Una cancelacion conserva los hashes, metadatos y resultados de la ultima
  corrida completa.
- Se recompilo `dist/MonitoreoWeb/MonitoreoWeb.exe` con los cambios.

**Motivo**

Evitar que una pagina problematica detenga todo el lote y ofrecer una salida
segura cuando una corrida deja de ser util o parece bloqueada.

**Verificacion**

- Ocho pruebas automatizadas: timeout con continuidad, cancelacion, excepcion
  inesperada, preservacion de datos, cierre de Playwright y endpoints de control.
- Validacion de sintaxis Python y `git diff --check`.
- Pruebas reales de navegador a 1280 y 360 px sin errores de consola ni
  desbordamiento horizontal.
- Simulacion de corrida activa con recuperacion tras recarga y cancelacion
  desde la interfaz.
- Recompilacion aislada con PyInstaller y prueba de humo del ejecutable sobre
  `/status`, la plantilla, las 35 URLs y la ruta activa de `urls.txt`.
- Una corrida real revelo un error al cerrar Playwright. Se separaron el
  administrador de contexto y la instancia activa, y se agrego una prueba de
  regresion que verifica el cierre correcto. La version compilada completo el
  mismo ciclo con Playwright real y una lista temporal vacia.

**ADR relacionado**

- `docs/adr/0006-controlar-corridas-prolongadas-y-cancelacion.md`

## 2026-08-25 - Actualizar fuentes monitoreadas

**Problema**

La lista activa de URLs necesitaba actualizar la fuente del Codigo Urbanistico
y de Edificacion e incorporar una nueva fuente de informes inmobiliarios.

**Cambio aplicado**

- Se retiro la URL anterior del Codigo Urbanistico y de Edificacion.
- Se incorporo la ruta correspondiente dentro del sitio historico del GCABA.
- Se agrego la pagina de reportes especiales 2026 de NMRK.

**Motivo**

Mantener la configuracion del monitoreo alineada con las fuentes que se quieren
seguir actualmente.

**Verificacion**

- Se comprobaron 35 URLs no vacias.
- Todas tienen formato absoluto HTTP o HTTPS.
- No se detectaron URLs duplicadas.
- `git diff --check`.

## 2026-07-15 - Adoptar interfaz operativa neutra

**Problema**

La interfaz dependia de un sistema visual institucional identificado como
`cpau-*` que habia sido eliminado. La estructura anterior tambien presentaba
todos los estados como tarjetas equivalentes, sin priorizar las novedades que
requieren atencion.

**Cambio aplicado**

- Se reemplazo la plantilla por una interfaz operativa neutra.
- Se separaron los estilos en `static/operational-ui.css`.
- Se agrego una banda de metricas con el total de fuentes procesadas.
- Los cambios detectados quedaron como contenido prioritario.
- Primer rastreo, revision manual y errores quedaron en secciones plegables.
- El gestor de URLs permanece cerrado por defecto y conserva la confirmacion de
  guardado junto al boton.
- Se eliminaron la fuente externa, el logotipo y las clases `cpau-*`.
- Se preservaron las rutas Flask, los formatos de datos y los IDs consumidos por
  JavaScript.

**Motivo**

Facilitar el trabajo diario con una jerarquia mas clara, una estetica neutral y
un sistema visual mantenible sin dependencias institucionales obsoletas.

**Verificacion**

- Pruebas Flask de la pagina, CSS y endpoints de lectura.
- Guardado de URLs simulado sin escribir `urls.txt`.
- Validacion de sintaxis Python e IDs HTML.
- Prueba de navegador con los 34 resultados y 34 URLs reales existentes.
- Alta de URL probada solo en memoria y descartada mediante recarga.
- Verificacion responsive a 1280, 980, 720 y 360 px sin desbordamiento.
- Consola del navegador sin errores de la aplicacion.
- `git diff --check`.

**ADR relacionado**

- `docs/adr/0005-adopt-operational-interface.md`

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
