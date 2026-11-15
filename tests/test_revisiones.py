"""Pruebas de la revisión de URLs sin cambios (etapa 1).

Usan fechas simuladas y una carpeta temporal: nunca leen ni escriben los datos
reales del proyecto.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import app as app_module
import monitor
import revisiones

URL_A = 'https://a.example/informes'
URL_B = 'https://b.example/novedades'


def dt(text):
    return datetime.fromisoformat(text)


class ReviewTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.urls_file = base / 'urls.txt'
        self.metadata_file = base / 'web_monitoring_metadata.json'
        self.results_file = base / 'last_run_results.json'
        self.hashes_file = base / 'web_monitoring_hashes.json'
        self.reviews_file = base / 'revisiones_urls.json'
        self.urls_file.write_text(f'{URL_A}\n{URL_B}\n', encoding='utf-8')
        self.write_metadata({
            URL_A: {'first_seen_at': '2026-07-01T08:00:00', 'last_status': 'Success',
                    'last_change_at': '2026-09-01T08:00:00',
                    'last_success_at': '2026-11-14T08:00:00', 'consecutive_unchanged_runs': 50},
            URL_B: {'first_seen_at': '2026-07-01T08:00:00', 'last_status': 'Success',
                    'last_change_at': '2026-11-10T08:00:00',
                    'last_success_at': '2026-11-14T08:00:00', 'consecutive_unchanged_runs': 3},
        })
        self.now = dt('2026-11-15T09:00:00')

        for item in (
            patch.object(monitor, 'URLS_FILE', self.urls_file),
            patch.object(monitor, 'METADATA_FILE', self.metadata_file),
            patch.object(monitor, 'RESULTS_FILE', self.results_file),
            patch.object(monitor, 'HASHES_FILE', self.hashes_file),
            patch.object(app_module, 'RESULTS_FILE', self.results_file),
            patch.object(revisiones, 'REVIEWS_FILE', self.reviews_file),
            patch.object(revisiones, '_now', side_effect=lambda: self.now),
            patch.object(monitor.time, 'sleep'),
        ):
            item.start()
            self.addCleanup(item.stop)

        self.client = app_module.app.test_client()
        with app_module._state_lock:
            app_module._state['running'] = False

    # -- utilidades -------------------------------------------------------

    def write_metadata(self, data):
        self.metadata_file.write_text(json.dumps(data), encoding='utf-8')

    def write_results(self, generated_at, review_urls):
        self.results_file.write_text(json.dumps({
            'generated_at': generated_at,
            'results': [],
            'review_items': [{'URL': url, 'DiasDesdeUltimoCambio': 75} for url in review_urls],
        }), encoding='utf-8')

    def stale_urls(self, now):
        items = monitor.build_review_items(
            monitor.load_metadata(), monitor.load_urls(), now, reviews=revisiones.load_reviews())
        return [item['URL'] for item in items]

    def results(self):
        return self.client.get('/results').get_json()

    def post(self, path, **body):
        return self.client.post(path, json=body)


class StaleReviewTests(ReviewTestBase):
    # -- R1: confirmar que no hubo novedades --------------------------------

    def test_confirmed_url_leaves_pending_list_immediately(self):
        self.write_results('2026-11-14T08:20:00', [URL_A])
        self.assertEqual([i['URL'] for i in self.results()['review_items']], [URL_A])

        response = self.post('/reviews/confirm', url=URL_A)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.results()['review_items'], [])

    def test_new_30_days_count_from_the_review(self):
        self.post('/reviews/confirm', url=URL_A)  # revisada el 2026-11-15 09:00
        self.assertNotIn(URL_A, self.stale_urls(dt('2026-12-15T08:59:00')))  # 29 días
        self.assertIn(URL_A, self.stale_urls(dt('2026-12-15T09:00:00')))     # 30 días

    def test_reappears_when_a_run_evaluates_it_after_the_new_deadline(self):
        self.post('/reviews/confirm', url=URL_A)
        # Corrida posterior al vencimiento: su lista incluye la URL y no se filtra.
        self.write_results('2026-12-16T08:20:00', [URL_A])
        self.assertEqual([i['URL'] for i in self.results()['review_items']], [URL_A])
        item = monitor.build_review_items(monitor.load_metadata(), [URL_A], dt('2026-12-16T08:00:00'),
                                          reviews=revisiones.load_reviews())[0]
        self.assertIn('última revisión manual', item['Motivo'])
        self.assertEqual(item['UltimoCambio'], '2026-09-01T08:00:00')

    def test_change_detected_before_deadline_restarts_count_from_detection(self):
        self.post('/reviews/confirm', url=URL_A)  # 2026-11-15
        metadata = monitor.load_metadata()
        metadata[URL_A]['last_change_at'] = '2026-11-25T08:00:00'
        self.write_metadata(metadata)
        self.assertNotIn(URL_A, self.stale_urls(dt('2026-12-20T08:00:00')))  # 25 días desde el cambio
        self.assertIn(URL_A, self.stale_urls(dt('2026-12-25T08:00:00')))     # 30 días desde el cambio

    def test_without_review_behaviour_is_unchanged(self):
        self.assertEqual(self.stale_urls(self.now), [URL_A])  # 75 días; URL_B solo 5

    # -- R2 y R3: clasificación ----------------------------------------------

    def test_undetected_changes_moves_url_to_review_section_with_cause(self):
        self.write_results('2026-11-14T08:20:00', [URL_A])
        response = self.post('/reviews/classify', url=URL_A, estado='a_revisar',
                             nota='El sitio publicó un informe nuevo en otra sección')
        self.assertEqual(response.status_code, 200)
        data = self.results()
        self.assertEqual(data['review_items'], [])
        self.assertEqual(len(data['to_review_items']), 1)
        item = data['to_review_items'][0]
        self.assertEqual(item['URL'], URL_A)
        self.assertEqual(item['Nota'], 'El sitio publicó un informe nuevo en otra sección')
        self.assertEqual(data['inactive_items'], [])
        # Se sigue monitoreando y no vuelve a la revisión por antigüedad.
        self.assertIn(URL_A, monitor.load_urls())
        self.assertNotIn(URL_A, self.stale_urls(dt('2027-03-01T08:00:00')))

    def test_inactive_site_shows_supporting_data_and_optional_note(self):
        response = self.post('/reviews/classify', url=URL_A, estado='inactivo')
        self.assertEqual(response.status_code, 200)
        item = self.results()['inactive_items'][0]
        self.assertEqual(item['Nota'], '')
        self.assertEqual(item['UltimaLecturaExitosa'], '2026-11-14T08:00:00')
        self.assertEqual(item['UltimoCambio'], '2026-09-01T08:00:00')

    def test_resolving_returns_to_normal_and_restarts_count(self):
        self.post('/reviews/classify', url=URL_A, estado='inactivo', nota='Sin publicaciones')
        self.now = dt('2026-11-20T10:00:00')
        response = self.post('/reviews/resolve', url=URL_A)
        self.assertEqual(response.status_code, 200)
        data = self.results()
        self.assertEqual(data['inactive_items'], [])
        self.assertNotIn(URL_A, self.stale_urls(dt('2026-12-19T10:00:00')))
        self.assertIn(URL_A, self.stale_urls(dt('2026-12-20T10:00:00')))

    # -- validaciones ----------------------------------------------------------

    def test_invalid_requests_save_nothing(self):
        cases = [
            ('/reviews/confirm', {'url': 'https://no-esta.example'}, 'no está en la lista'),
            ('/reviews/classify', {'url': URL_A, 'estado': 'otra'}, 'no reconocida'),
            ('/reviews/resolve', {'url': URL_A}, 'no está en'),
        ]
        for path, body, fragment in cases:
            with self.subTest(path=path):
                response = self.post(path, **body)
                self.assertEqual(response.status_code, 400)
                self.assertIn(fragment, response.get_json()['error'])
                self.assertFalse(self.reviews_file.exists())

    def test_removed_source_is_not_shown_in_sections(self):
        self.post('/reviews/classify', url=URL_A, estado='a_revisar')
        self.urls_file.write_text(f'{URL_B}\n', encoding='utf-8')
        self.assertEqual(self.results()['to_review_items'], [])

    def test_damaged_reviews_file_does_not_block_monitoring(self):
        self.reviews_file.write_text('{ dañado', encoding='utf-8')
        self.assertEqual(revisiones.load_reviews(), {})
        self.assertEqual(self.stale_urls(self.now), [URL_A])

    def test_page_offers_review_actions_and_sections(self):
        html = self.client.get('/').get_data(as_text=True)
        for fragment in ('Sin novedades', 'Cambios no detectados', 'Sitio inactivo o caído',
                         'Marcar como resuelta', 'id="list-to-review"', 'id="list-inactive"',
                         "'/reviews/confirm'", "'/reviews/classify'", "'/reviews/resolve'",
                         'Nota (opcional)'):
            self.assertIn(fragment, html)

    # -- revisión durante una corrida ------------------------------------------

    def test_review_during_a_run_is_allowed_and_not_lost(self):
        async def fake_process(urls, **kwargs):
            # Mientras la corrida está en curso, la persona clasifica una URL.
            with app_module._state_lock:
                app_module._state['running'] = True
            response = self.post('/reviews/classify', url=URL_A, estado='a_revisar', nota='x')
            with app_module._state_lock:
                app_module._state['running'] = False
            self.assertEqual(response.status_code, 200)
            return [(url, 'Success', 'texto', '') for url in urls]

        self.hashes_file.write_text(json.dumps({
            URL_A: monitor.calculate_hash('texto'), URL_B: monitor.calculate_hash('texto')}),
            encoding='utf-8')
        with patch.object(monitor, 'process_urls', new=fake_process):
            monitor.run_monitor()

        self.assertEqual(revisiones.load_reviews()[URL_A]['estado'], 'a_revisar')
        saved = json.loads(self.results_file.read_text(encoding='utf-8'))
        self.assertNotIn(URL_A, [item['URL'] for item in saved['review_items']])
        self.assertEqual(self.results()['to_review_items'][0]['URL'], URL_A)


if __name__ == '__main__':
    unittest.main()
