"""Pruebas del guardado de una corrida completada (etapa 1 del aviso de repetición).

Cada prueba trabaja en una carpeta temporal con archivos reales: nunca toca los
datos del proyecto. La conservación se comprueba comparando el contenido
exacto de los archivos antes y después, no solo la cantidad de filas.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import monitor
import revisiones

URL_A = 'https://a.example'
URL_B = 'https://b.example'

PREVIOUS_HASHES = {URL_A: 'hash-anterior-a', URL_B: 'hash-anterior-b'}
PREVIOUS_METADATA = {URL_A: {'first_seen_at': '2026-11-01T08:00:00'}}
PREVIOUS_RESULTS = {
    'generated_at': '2026-11-14T08:20:00',
    'results': [{'URL': URL_A, 'Estado': 'Success',
                 'Resultado': 'Cambio detectado', 'Error': ''}],
    'review_items': [],
}


def fake_process(raw_results):
    """Reemplaza la lectura de sitios por resultados fijos."""
    async def _process(urls, **kwargs):
        return raw_results
    return _process


class SaveRunOutputsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.files = {
            'results': self.base / 'last_run_results.json',
            'metadata': self.base / 'web_monitoring_metadata.json',
            'hashes': self.base / 'web_monitoring_hashes.json',
        }
        self.files['results'].write_text(json.dumps(PREVIOUS_RESULTS), encoding='utf-8')
        self.files['metadata'].write_text(json.dumps(PREVIOUS_METADATA), encoding='utf-8')
        self.files['hashes'].write_text(json.dumps(PREVIOUS_HASHES), encoding='utf-8')
        self.original_bytes = self.snapshot()

        self._patches = [
            patch.object(monitor, 'RESULTS_FILE', self.files['results']),
            patch.object(monitor, 'METADATA_FILE', self.files['metadata']),
            patch.object(monitor, 'HASHES_FILE', self.files['hashes']),
            patch.object(monitor, 'load_urls', return_value=[URL_A, URL_B]),
            patch.object(revisiones, 'REVIEWS_FILE', self.base / 'revisiones_urls.json'),
            patch.object(monitor.time, 'sleep'),
        ]
        for item in self._patches:
            item.start()

    def tearDown(self):
        for item in reversed(self._patches):
            item.stop()
        self._tmp.cleanup()

    # -- utilidades -------------------------------------------------------

    def snapshot(self):
        return {name: path.read_bytes() for name, path in self.files.items()}

    def read(self, name):
        return json.loads(self.files[name].read_text(encoding='utf-8'))

    def leftover_temp_files(self):
        return sorted(p.name for p in self.base.glob('*.tmp'))

    def run_with(self, raw_results):
        with patch.object(monitor, 'process_urls', new=fake_process(raw_results)):
            return monitor.run_monitor()

    def result_for(self, url):
        rows = self.read('results')['results']
        return next(row for row in rows if row['URL'] == url)

    # -- corrida normal (R4) ----------------------------------------------

    def test_completed_run_replaces_all_three_files(self):
        self.run_with([
            (URL_A, 'Success', 'contenido nuevo A', ''),
            (URL_B, 'Success', 'contenido nuevo B', ''),
        ])

        self.assertEqual(self.result_for(URL_A)['Resultado'], 'Cambio detectado')
        self.assertEqual(self.result_for(URL_B)['Resultado'], 'Cambio detectado')
        self.assertEqual(
            self.read('hashes')[URL_A],
            monitor.calculate_hash(monitor.clean_text('contenido nuevo A')),
        )
        self.assertIn('last_change_at', self.read('metadata')[URL_A])
        self.assertNotEqual(self.read('results')['generated_at'],
                            PREVIOUS_RESULTS['generated_at'])
        self.assertEqual(self.leftover_temp_files(), [])

    def test_zero_novelties_is_a_valid_result_and_replaces_previous(self):
        same_hash_text = 'texto estable'
        stable_hash = monitor.calculate_hash(monitor.clean_text(same_hash_text))
        self.files['hashes'].write_text(
            json.dumps({URL_A: stable_hash, URL_B: stable_hash}), encoding='utf-8')

        self.run_with([
            (URL_A, 'Success', same_hash_text, ''),
            (URL_B, 'Success', same_hash_text, ''),
        ])

        resultados = [row['Resultado'] for row in self.read('results')['results']]
        self.assertEqual(resultados, ['Sin cambios', 'Sin cambios'])

    # -- fuentes con error (R3 y R6) ---------------------------------------

    def test_run_with_source_errors_completes_and_reports_them(self):
        self.run_with([
            (URL_A, 'Success', 'contenido nuevo A', ''),
            (URL_B, 'Error', '', 'HTTP 503'),
        ])

        fila_b = self.result_for(URL_B)
        self.assertEqual(fila_b['Resultado'], 'Error de lectura')
        self.assertEqual(fila_b['Error'], 'HTTP 503')
        self.assertEqual(self.result_for(URL_A)['Resultado'], 'Cambio detectado')

    def test_source_with_error_keeps_its_last_valid_reference(self):
        self.run_with([
            (URL_A, 'Success', 'contenido nuevo A', ''),
            (URL_B, 'Error', '', 'HTTP 503'),
        ])

        hashes = self.read('hashes')
        self.assertEqual(hashes[URL_B], PREVIOUS_HASHES[URL_B])
        self.assertNotEqual(hashes[URL_A], PREVIOUS_HASHES[URL_A])

    # -- cancelación (R5) --------------------------------------------------

    def test_cancelled_run_leaves_files_byte_identical(self):
        async def cancelled(urls, **kwargs):
            raise monitor.RunCancelled()

        with patch.object(monitor, 'process_urls', new=cancelled):
            with self.assertRaises(monitor.RunCancelled):
                monitor.run_monitor()

        self.assertEqual(self.snapshot(), self.original_bytes)

    # -- fallos de guardado -----------------------------------------------

    def test_failure_while_preparing_drafts_keeps_every_previous_file(self):
        real_write = monitor._write_temp_json
        calls = {'count': 0}

        def failing_on_second(target, data):
            calls['count'] += 1
            if calls['count'] == 2:  # falla al preparar los metadatos
                raise OSError('disco lleno simulado')
            return real_write(target, data)

        with patch.object(monitor, '_write_temp_json', side_effect=failing_on_second):
            with self.assertRaises(OSError):
                self.run_with([(URL_A, 'Success', 'contenido nuevo A', ''),
                               (URL_B, 'Success', 'contenido nuevo B', '')])

        self.assertEqual(self.snapshot(), self.original_bytes)
        self.assertEqual(self.leftover_temp_files(), [])

    def test_cut_after_results_replaced_repeats_novelty_instead_of_losing_it(self):
        real_replace = os.replace
        calls = {'count': 0}

        def cut_after_first(src, dst):
            calls['count'] += 1
            if calls['count'] == 2:  # se corta antes de los metadatos
                raise OSError('corte simulado')
            return real_replace(src, dst)

        with patch.object(monitor._os, 'replace', side_effect=cut_after_first):
            with self.assertRaises(OSError):
                self.run_with([(URL_A, 'Success', 'contenido nuevo A', ''),
                               (URL_B, 'Success', 'contenido nuevo B', '')])

        # La pantalla ya muestra la novedad, pero las referencias no cambiaron.
        self.assertEqual(self.result_for(URL_A)['Resultado'], 'Cambio detectado')
        self.assertEqual(self.read('hashes'), PREVIOUS_HASHES)
        self.assertEqual(self.leftover_temp_files(), [])

        # La corrida siguiente vuelve a mostrar la novedad: no se pierde.
        self.run_with([(URL_A, 'Success', 'contenido nuevo A', ''),
                       (URL_B, 'Success', 'contenido nuevo B', '')])
        self.assertEqual(self.result_for(URL_A)['Resultado'], 'Cambio detectado')

    def test_file_temporarily_locked_is_retried(self):
        real_replace = os.replace
        calls = {'count': 0}

        def locked_once(src, dst):
            calls['count'] += 1
            if calls['count'] == 1:
                raise PermissionError('archivo abierto por otro programa')
            return real_replace(src, dst)

        with patch.object(monitor._os, 'replace', side_effect=locked_once):
            self.run_with([(URL_A, 'Success', 'contenido nuevo A', ''),
                           (URL_B, 'Success', 'contenido nuevo B', '')])

        self.assertEqual(self.result_for(URL_A)['Resultado'], 'Cambio detectado')
        self.assertNotEqual(self.read('hashes'), PREVIOUS_HASHES)
        self.assertEqual(self.leftover_temp_files(), [])


if __name__ == '__main__':
    unittest.main()
