# 0005 - Adoptar una interfaz operativa neutra

## Estado

Reemplazado por `0010-adoptar-estilo-cpau.md` (2026-11-16).

## Fecha

2026-07-15

## Contexto

La interfaz web utilizaba un sistema visual institucional identificado en el
código como `cpau-*`, con logotipo, tipografía externa y componentes propios de
ese estilo. Ese sistema fue retirado y dejó de ser una referencia vigente para
la aplicación.

La herramienta se usa para una tarea operativa diaria: ejecutar el monitoreo,
identificar novedades, revisar excepciones y mantener una lista de URLs. La
interfaz debía priorizar esas tareas sin cambiar los endpoints, formatos de
datos ni archivos persistentes ya validados.

## Decisión

Adoptar un sistema visual neutro y orientado a tareas con estas reglas:

- hoja de estilos separada en `static/operational-ui.css`;
- tipografía del sistema, sin fuentes externas ni logotipo institucional;
- lienzo gris claro, superficies blancas y azul marino para la acción principal;
- colores semánticos suaves para cambios, revisión, información y errores;
- banda compacta de métricas y cambios detectados como contenido prioritario;
- estados secundarios plegables y gestor de URLs cerrado por defecto;
- conservación de los IDs, rutas, métodos y cuerpos de las APIs existentes;
- adaptación sin desbordamiento horizontal a 1280, 980, 720 y 360 px.

## Alternativas consideradas

- **Mantener el estilo anterior:** descartado porque la referencia institucional
  fue eliminada y conservarla generaría una dependencia obsoleta.
- **Sobrescribir visualmente las clases `cpau-*`:** descartado porque mantendría
  nombres y reglas heredadas difíciles de comprender y mantener.
- **Integrar el prototipo neutro preservando contratos:** opción elegida porque
  separa presentación y comportamiento sin agregar dependencias.

## Consecuencias

- La interfaz deja de depender de recursos visuales externos.
- Los cambios visuales futuros deben reutilizar los tokens `--ui-*` y preservar
  los contratos funcionales documentados.
- El CSS queda en un archivo independiente incluido automáticamente por
  PyInstaller junto con la carpeta `static`.
- La nueva composición mejora la lectura de estados, pero su eficacia cotidiana
  deberá seguir evaluándose con corridas reales.

## Verificación

- Pruebas Flask de `/`, `/results`, `/urls` y recurso CSS.
- Guardado simulado reemplazando temporalmente la escritura real.
- Validación de IDs únicos y contratos HTML preservados.
- Prueba de navegador sobre resultados reales sin ejecutar una corrida.
- Prueba de alta de URL sólo en memoria, descartada mediante recarga.
- Verificación responsive a 1280, 980, 720 y 360 px sin desbordamiento horizontal.
- Consola del navegador sin errores de la aplicación.
