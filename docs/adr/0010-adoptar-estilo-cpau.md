# 0010 - Adoptar la identidad visual de la Biblioteca CPAU

## Estado

Aceptado. Reemplaza al ADR 0005.

## Fecha

2026-11-16

## Contexto

Desde el ADR 0005 la interfaz usaba un sistema visual neutro
(`static/operational-ui.css`). La persona usuaria pidió aplicar el estilo de la
Biblioteca CPAU, que hoy cuenta con un kit para aplicaciones locales (skill
`cpau-estilo`): paleta del Manual normativo CPAU 2019, Roboto instalada,
estética plana y funcionamiento sin conexión.

También pidió que los cuadros de resultados queden uno debajo del otro y a todo
el ancho, para que entren mejor los botones de revisión. La columna lateral
angosta obligaba a apilar los botones y a desplazar listas dentro de cada
cuadro.

## Decisión

- Nueva hoja de estilos `static/cpau-ui.css`, derivada de la anterior: se
  conservan las clases y la estructura y se reemplazan los valores por la
  identidad CPAU.
  - Fondo #f7f6f5, superficies blancas, bordes #e0dbd9 y #bfb5ab, texto negro y
    gris #616161.
  - Azul #3400ff solo para la acción principal, enlaces, antetítulos y filetes
    de la tarjeta de ejecución y de los indicadores.
  - Roboto; sin sombras ni degradés; esquinas de 2 px.
  - Colores de estado (verde, ámbar, rojo) como extensión funcional, siempre con
    texto.
- Barra superior con el logo «Biblioteca CPAU» (`static/logo-biblioteca.png`),
  filete negro y el nombre «Monitor web · Selección informativa». Ícono de
  pestaña con la «A» del logo (`static/favicon.ico`). Pie «Biblioteca CPAU ·
  Monitor web».
- Resultados en una sola columna, a todo el ancho y en el orden existente. Las
  listas crecen con la página en lugar de desplazarse dentro de cada cuadro.
- No se modifican IDs, endpoints, comportamiento de JavaScript ni datos.

## Alternativas consideradas

- **Migrar todas las clases al kit `cpau-app.css`:** alinea por completo con el
  kit, pero obliga a reescribir el HTML que genera el JavaScript (resultados,
  revisiones, fuentes), con riesgo de romper funciones ya probadas.
- **Mantener el estilo neutro y cambiar solo la diagramación:** no cumple el
  pedido de identidad institucional.

## Consecuencias

- La interfaz deja de seguir la skill `disenar-interfaces-operativas`; los
  cambios visuales futuros se rigen por `cpau-estilo`.
- `static/operational-ui.css` se elimina.
- La página es más larga: los cuadros ocupan todo el ancho y las listas no
  tienen desplazamiento interno.

## Verificación

- Prototipo sobre una copia con datos reales, revisado y aprobado por la persona
  usuaria antes de aplicarlo.
- Capturas a 1366 px y 390 px: sin desplazamiento horizontal ni errores de
  consola.
- Pruebas automáticas completas y verificación del ejecutable recompilado.
