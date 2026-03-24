# Redesign

Este directorio deja asentado el replanteo del monitor sin tocar la app actual.

## Diagnostico

La version actual usa Playwright para demasiados sitios y ejecuta el scraping dentro
de la misma app web. En Hugging Face Spaces eso termino siendo fragil.

El prototipo original en Colab y las pruebas actuales muestran que no todos los
sitios necesitan la misma estrategia:

- varios funcionan bien con `requests + BeautifulSoup`
- varios requieren parsear solo una seccion concreta, no el `body` completo
- unos pocos estan protegidos o cargan contenido de forma mas dinamica
- Zonaprop ya es un caso especial y no conviene tratarlo como una pagina comun

## Objetivo del redisenio

Pasar de una estrategia "Playwright para casi todo" a una estrategia por tipo de sitio.

## Tipos de estrategia

- `static_text`
  Usa `requests + BeautifulSoup` y hash del texto visible de una pagina concreta.
  Sirve cuando la pagina de interes es relativamente estable y el cambio relevante
  ocurre en el propio contenido de la pagina.

- `structured_listing`
  Usa `requests + BeautifulSoup`, pero en vez de hashear todo el `body`, extrae una
  lista estructurada de items relevantes: titulos, fechas, links a PDF, cards o
  noticias.
  Esta deberia ser la estrategia por defecto del redisenio.

- `special_pdf_probe`
  No scrapea la pagina principal. Busca directamente un PDF esperado o un patron
  de archivo publicado mensualmente.
  Hoy aplica a Zonaprop.

- `playwright_listing`
  Usa Playwright solo para obtener una seccion dinamica concreta de la pagina, no
  el texto completo del `body`.
  Debe reservarse para dominios realmente problematicos.

- `playwright_fallback`
  Intenta primero una estrategia con `requests`; si hay bloqueo, contenido vacio o
  HTML insuficiente, recien ahi cae a Playwright.

- `gdrive_folder`
  Estrategia especial para carpetas publicas de Google Drive. El criterio de cambio
  debe basarse en archivos visibles y metadatos relevantes, no en el nombre de la
  pagina.

## Principios de implementacion

- `requests` primero; Playwright solo cuando haga falta.
- Parsear la seccion correcta del sitio en lugar del `body` completo.
- Hashear una representacion estable y pequena.
- Mantener las estrategias especiales por dominio o URL.
- Separar el scraping pesado de la app web cuando se retome la arquitectura general.

## Orden sugerido de implementacion

1. Migrar a `structured_listing` todos los sitios que hoy son estaticos.
2. Mantener `special_pdf_probe` para Zonaprop.
3. Agregar `playwright_listing` o `playwright_fallback` solo para dominios bloqueados.
4. Agregar `gdrive_folder` para la carpeta publica de Google Drive de UdeSA.

## Archivo clave

- `url_strategy_matrix.csv`

Ese archivo es la matriz inicial de decisiones por URL y deberia ser la base para
la proxima implementacion.
