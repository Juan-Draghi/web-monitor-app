"""Pruebas de la lectura de INDEC por su informe PDF.

No acceden a internet: la respuesta de INDEC se simula con un fragmento de HTML
como el que devuelve la dirección interna.
"""

import asyncio
import unittest
from unittest.mock import MagicMock

import monitor

PAGE = 'https://www.indec.gob.ar/indec/web/Nivel3-Tema-3-3'
DATA = 'https://www.indec.gob.ar/Nivel3/Tema/3/3'

FRAGMENT = """
<div class="ruta-texto"><a onclick="navpage(this);" data-view="Portada">Inicio</a> > Economía</div>
<div>Actividad de la construcción 5,1% Variación interanual Septiembre 2026</div>
<div>Informes técnicos 06/11/2026 Indicadores de coyuntura de la actividad de la construcción
  <a href="/uploads/informesdeprensa/isac_11_26F4E69BED3F.pdf">Ver Informe</a></div>
"""


def fake_session(html, status=200):
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=status, text=html)
    return session


class IndecTests(unittest.TestCase):
    def test_page_url_maps_to_internal_data_url(self):
        self.assertTrue(monitor.is_indec_page(PAGE))
        self.assertEqual(monitor.indec_data_url(PAGE), DATA)
        self.assertEqual(monitor.indec_data_url(PAGE + '?x=1#y'), DATA)
        self.assertFalse(monitor.is_indec_page('https://www.ieric.org.ar/novedades/'))

    def test_reads_report_pdf_link(self):
        session = fake_session(FRAGMENT)
        pdf, error = monitor.fetch_indec_report_pdf(PAGE, session)
        self.assertEqual(pdf, 'https://www.indec.gob.ar/uploads/informesdeprensa/isac_11_26F4E69BED3F.pdf')
        self.assertEqual(error, '')
        self.assertEqual(session.get.call_args[0][0], DATA)

    def test_missing_pdf_is_an_error_not_unchanged(self):
        result = asyncio.run(monitor.fetch_url(fake_session('<div>Solo menú</div>'), PAGE))
        self.assertEqual(result[1], 'Error')
        self.assertIn('no se encontró el enlace al informe PDF', result[3])

    def test_http_error_is_reported(self):
        result = asyncio.run(monitor.fetch_url(fake_session('', status=503), PAGE))
        self.assertEqual(result[1], 'Error')
        self.assertIn('HTTP 503', result[3])

    def test_compared_content_is_only_the_pdf_link(self):
        _, status, text, _ = asyncio.run(monitor.fetch_url(fake_session(FRAGMENT), PAGE))
        self.assertEqual(status, 'Success')
        self.assertEqual(text, 'PDF_URL: https://www.indec.gob.ar/uploads/informesdeprensa/isac_11_26F4E69BED3F.pdf')
        # Un cambio de cifras o de menú sin informe nuevo no altera lo comparado.
        noisy = FRAGMENT.replace('5,1%', '5,2%').replace('Inicio', 'Portada')
        _, _, text_noisy, _ = asyncio.run(monitor.fetch_url(fake_session(noisy), PAGE))
        self.assertEqual(text_noisy, text)
        # Un informe nuevo sí lo altera.
        newer = FRAGMENT.replace('isac_11_26F4E69BED3F', 'isac_12_26AAAA')
        _, _, text_new, _ = asyncio.run(monitor.fetch_url(fake_session(newer), PAGE))
        self.assertNotEqual(text_new, text)

    def test_page_shows_pdf_link_when_available(self):
        import app as app_module
        html = app_module.app.test_client().get('/').get_data(as_text=True)
        self.assertIn('Abrir informe PDF', html)
        self.assertIn('item.Documento', html)

    def test_document_link_extracted_for_results(self):
        self.assertEqual(monitor.document_url_from_content('PDF_URL: https://x.example/a.pdf'),
                         'https://x.example/a.pdf')
        self.assertEqual(monitor.document_url_from_content('texto común'), '')


if __name__ == '__main__':
    unittest.main()
