# TODO

## Proxima mejora

- Integrar al monitoreo la carpeta publica de Google Drive de la Universidad de San Andres:
  `https://drive.google.com/drive/folders/1WLhgl6g9XmBVZzhvWFHhr1F2t7BX3srC`

## Objetivo funcional

- Detectar la publicacion mensual de 3 archivos:
  - informe
  - presentacion
  - infografia
- Identificar nuevas publicaciones por fecha de publicacion del archivo, no por nombre.

## Contexto

- El sitio web de la Universidad de San Andres enlaza a esa carpeta publica para acceder a los informes.
- Los nombres de los archivos varian, por eso el criterio correcto de deteccion debe ser la fecha de publicacion.
- Ya existe una base para este trabajo en `app.py` con la funcion `fetch_gdrive_folder`.

## Cuando retomarlo

- Implementarlo una vez que el nuevo Hugging Face Space haya demostrado estabilidad durante varios dias.
