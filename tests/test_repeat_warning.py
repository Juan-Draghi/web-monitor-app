"""Pruebas del aviso de repetición (etapa 2).

Usan un archivo de resultados temporal y una hora simulada: nunca leen ni
escriben los datos reales del proyecto.
"""

import json
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import app as app_module


def at(text):
    return datetime.fromisoformat('2026-11-15T' + text)


class RepeatWarningTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.results_file = Path(self._tmp.name) / 'last_run_results.json'
        self.client = app_module.app.test_client()
        self.run_monitor_calls = 0
        self.run_monitor_error = None

        def fake_run_monitor(**kwargs):
            self.run_monitor_calls += 1
            if self.run_monitor_error:
                raise self.run_monitor_error

        patches = [
            patch.object(app_module, 'RESULTS_FILE', self.results_file),
            patch.object(app_module, 'load_urls', return_value=['https://a.example']),
            patch.object(app_module, 'run_monitor', side_effect=fake_run_monitor),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self._tmp.cleanup)

        with app_module._state_lock:
            app_module._state.update({'running': False, 'run_state': 'idle', 'message': ''})

    # -- utilidades -------------------------------------------------------

    def last_completed(self, hhmmss):
        self.results_file.write_text(json.dumps({
            'generated_at': '2026-11-15T' + hhmmss,
            'results': [{'URL': 'https://a.example', 'Resultado': 'Cambio detectado'}],
            'review_items': [],
        }), encoding='utf-8')

    def request_run(self, now, confirm=None):
        body = {} if confirm is None else {'confirm_repeat': confirm}
        with patch.object(app_module, '_now', return_value=now):
            response = self.client.post('/run', json=body)
        self.wait_until_idle()
        return response

    def wait_until_idle(self):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with app_module._state_lock:
                if not app_module._state['running']:
                    return
            time.sleep(0.01)
        self.fail('La corrida simulada no terminó')

    def assert_warning(self, response, minutes):
        self.assertEqual(response.status_code, 409)
        data = response.get_json()
        self.assertTrue(data['confirmation_required'])
        self.assertEqual(data['minutes_since'], minutes)
        self.assertEqual(self.run_monitor_calls, 0, 'No debía iniciarse ninguna corrida')

    def assert_started(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'started'})
        self.assertEqual(self.run_monitor_calls, 1)

    # -- ejemplos de aceptación -------------------------------------------

    def test_59_minutes_after_completion_shows_warning(self):
        self.last_completed('08:00:00')
        self.assert_warning(self.request_run(at('08:59:00')), 59)

    def test_one_second_before_60_minutes_still_shows_warning(self):
        self.last_completed('08:00:00')
        self.assert_warning(self.request_run(at('08:59:59')), 59)

    def test_exactly_60_minutes_does_not_show_warning(self):
        self.last_completed('08:00:00')
        self.assert_started(self.request_run(at('09:00:00')))

    def test_counts_from_end_of_run_not_from_start(self):
        # Corrida de 8:00 a 8:20; pedido a las 9:05 -> 45 minutos.
        self.last_completed('08:20:00')
        self.assert_warning(self.request_run(at('09:05:00')), 45)

    def test_no_previous_run_does_not_show_warning(self):
        self.assert_started(self.request_run(at('09:00:00')))

    def test_unreadable_results_file_does_not_block_running(self):
        self.results_file.write_text('{ archivo dañado', encoding='utf-8')
        self.assert_started(self.request_run(at('09:00:00')))

    def test_declining_leaves_results_file_byte_identical(self):
        # "No ejecutar" no llama al servidor; la consulta previa tampoco escribe.
        self.last_completed('08:00:00')
        before = self.results_file.read_bytes()
        self.assert_warning(self.request_run(at('08:30:00')), 30)
        self.assertEqual(self.results_file.read_bytes(), before)
        with app_module._state_lock:
            self.assertEqual(app_module._state['run_state'], 'idle')

    def test_confirmation_starts_the_run(self):
        self.last_completed('08:00:00')
        self.assert_started(self.request_run(at('08:30:00'), confirm=True))

    def test_only_explicit_true_counts_as_confirmation(self):
        self.last_completed('08:00:00')
        self.assert_warning(self.request_run(at('08:30:00'), confirm='true'), 30)

    def test_failed_attempt_does_not_restart_the_60_minutes(self):
        self.last_completed('08:00:00')
        self.run_monitor_error = RuntimeError('fallo simulado')
        self.request_run(at('08:30:00'), confirm=True)
        with app_module._state_lock:
            self.assertEqual(app_module._state['run_state'], 'failed')

        self.run_monitor_calls = 0
        self.assert_warning(self.request_run(at('08:35:00')), 35)

    def test_page_contains_repeat_warning_controls(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('id="repeat-warning"', html)
        self.assertIn('Ejecutar igual', html)
        self.assertIn('No ejecutar', html)
        self.assertIn('confirm_repeat', html)


if __name__ == '__main__':
    unittest.main()
