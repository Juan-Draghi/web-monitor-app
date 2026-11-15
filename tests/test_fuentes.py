"""Pruebas del historial de fuentes (etapa 1).

Trabajan sobre una carpeta temporal: nunca tocan urls.txt ni el historial
reales. La conservación se comprueba comparando el contenido exacto.
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import app as app_module
import fuentes
import monitor

URL_1 = 'https://uno.example/informes'
URL_2 = 'https://dos.example/novedades'
URL_NUEVA = 'https://tres.example/blog'
FECHA = datetime(2026, 11, 16, 9, 20)


class SourcesTestBase(unittest.TestCase):
    """Carpeta temporal con urls.txt e historial propios para cada prueba."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.urls_file = self.base / 'urls.txt'
        self.history_file = self.base / 'historial_fuentes.md'
        self.urls_file.write_text(f'{URL_1}\n{URL_2}\n', encoding='utf-8')

        for item in (
            patch.object(monitor, 'URLS_FILE', self.urls_file),
            patch.object(app_module, 'URLS_FILE', self.urls_file),
            patch.object(fuentes, 'HISTORY_FILE', self.history_file),
            patch.object(fuentes, '_now', return_value=FECHA),
            patch.object(monitor.time, 'sleep'),
        ):
            item.start()
            self.addCleanup(item.stop)

        self.client = app_module.app.test_client()
        with app_module._state_lock:
            app_module._state['running'] = False

    # -- utilidades -------------------------------------------------------

    def post(self, path, **body):
        return self.client.post(path, json=body)

    def urls(self):
        return self.urls_file.read_text(encoding='utf-8').splitlines()

    def history(self):
        return self.history_file.read_text(encoding='utf-8')

    def snapshot(self):
        return {
            path.name: (path.read_bytes() if path.exists() else None)
            for path in (self.urls_file, self.history_file)
        }

    def leftover_temp_files(self):
        return sorted(p.name for p in self.base.glob('*.tmp'))

    def assert_rejected(self, response, status, fragment, before):
        self.assertEqual(response.status_code, status)
        self.assertIn(fragment, response.get_json()['error'])
        self.assertEqual(self.snapshot(), before, 'No debía cambiar ningún archivo')
        self.assertEqual(self.leftover_temp_files(), [])


class SourceHistoryTests(SourcesTestBase):
    # -- inventario inicial ------------------------------------------------

    def test_history_starts_with_inventory_of_current_sources(self):
        self.assertTrue(fuentes.ensure_history())
        text = self.history()
        self.assertIn('# Historial de fuentes', text)
        self.assertIn('## 2026-11-16 09:20 · Inventario inicial', text)
        self.assertIn('- Fuentes (2):', text)
        self.assertIn(f'  - {URL_1}', text)
        self.assertIn(f'  - {URL_2}', text)
        # Si ya existe, no se vuelve a crear.
        self.assertFalse(fuentes.ensure_history())
        self.assertEqual(self.history(), text)

    # -- R1: motivo obligatorio --------------------------------------------

    def test_missing_reason_rejects_every_operation_without_changes(self):
        before = self.snapshot()
        for path, body in (
            ('/urls/add', {'url': URL_NUEVA, 'motivo': ''}),
            ('/urls/remove', {'url': URL_1, 'motivo': '   '}),
            ('/urls/update', {'url_anterior': URL_1, 'url': URL_NUEVA}),
        ):
            with self.subTest(path=path):
                self.assert_rejected(self.post(path, **body), 400, 'motivo', before)

    # -- R2: registro de cada cambio ---------------------------------------

    def test_add_appends_source_and_records_reason(self):
        response = self.post('/urls/add', url=URL_NUEVA, motivo='Publica informes trimestrales')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.urls(), [URL_1, URL_2, URL_NUEVA])
        self.assertIn(
            '## 2026-11-16 09:20 · Alta\n'
            f'- URL: {URL_NUEVA}\n'
            '- Motivo: Publica informes trimestrales\n',
            self.history(),
        )

    def test_update_replaces_in_place_and_records_both_urls(self):
        response = self.post('/urls/update', url_anterior=URL_1, url=URL_NUEVA,
                             motivo='El sitio trasladó la sección')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.urls(), [URL_NUEVA, URL_2])
        self.assertIn(
            '## 2026-11-16 09:20 · Modificación\n'
            f'- URL: {URL_NUEVA}\n'
            f'- URL anterior: {URL_1}\n'
            '- Motivo: El sitio trasladó la sección\n',
            self.history(),
        )

    # -- R3 y R4: baja con seguimiento manual ------------------------------

    def test_remove_for_unresolved_reading_records_manual_followup(self):
        response = self.post('/urls/remove', url=URL_2, seguimiento_manual=True,
                             motivo='Lectura no resuelta: la página carga por JavaScript')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.urls(), [URL_1])
        self.assertIn(
            '## 2026-11-16 09:20 · Baja\n'
            f'- URL: {URL_2}\n'
            '- Motivo: Lectura no resuelta: la página carga por JavaScript\n'
            '- Seguimiento manual fuera de la aplicación: sí\n',
            self.history(),
        )
        # No queda ninguna lista interna de seguimiento: la URL sale de la lista activa.
        self.assertNotIn(URL_2, self.client.get('/urls').get_json()['urls'])

    def test_remove_without_followup_records_no(self):
        self.post('/urls/remove', url=URL_2, motivo='Duplicaba otra fuente')
        self.assertIn('- Seguimiento manual fuera de la aplicación: no\n', self.history())

    def test_successive_changes_keep_previous_records(self):
        self.post('/urls/add', url=URL_NUEVA, motivo='Primera')
        after_first = self.history()
        self.post('/urls/remove', url=URL_1, motivo='Segunda')
        after_second = self.history()
        self.post('/urls/update', url_anterior=URL_2, url='https://dos.example/v2', motivo='Tercera')
        final = self.history()

        self.assertTrue(after_second.startswith(after_first.rstrip('\n')))
        self.assertTrue(final.startswith(after_second.rstrip('\n')))
        positions = [final.index(text) for text in
                     ('Inventario inicial', 'Motivo: Primera', 'Motivo: Segunda', 'Motivo: Tercera')]
        self.assertEqual(positions, sorted(positions))

    def test_multiline_reason_is_saved_in_one_line(self):
        self.post('/urls/add', url=URL_NUEVA, motivo='Línea uno\n  línea dos')
        self.assertIn('- Motivo: Línea uno línea dos\n', self.history())

    # -- validaciones --------------------------------------------------------

    def test_invalid_requests_change_nothing(self):
        fuentes.ensure_history()
        before = self.snapshot()
        cases = [
            ('/urls/add', {'url': URL_1, 'motivo': 'x'}, 'ya está'),
            ('/urls/add', {'url': 'www.sin-protocolo.com', 'motivo': 'x'}, 'http'),
            ('/urls/add', {'url': 'https://con espacio.com', 'motivo': 'x'}, 'espacios'),
            ('/urls/remove', {'url': URL_NUEVA, 'motivo': 'x'}, 'no está'),
            ('/urls/update', {'url_anterior': URL_1, 'url': URL_2, 'motivo': 'x'}, 'ya está'),
            ('/urls/update', {'url_anterior': URL_1, 'url': URL_1, 'motivo': 'x'}, 'igual'),
        ]
        for path, body, fragment in cases:
            with self.subTest(path=path, body=body):
                self.assert_rejected(self.post(path, **body), 400, fragment, before)

    def test_changes_are_blocked_during_a_run(self):
        before = self.snapshot()
        with app_module._state_lock:
            app_module._state['running'] = True
        try:
            response = self.post('/urls/add', url=URL_NUEVA, motivo='x')
        finally:
            with app_module._state_lock:
                app_module._state['running'] = False
        self.assert_rejected(response, 409, 'corrida', before)

    def test_page_uses_one_operation_per_change_with_reason(self):
        html = self.client.get('/').get_data(as_text=True)
        for fragment in ("'/urls/add'", "'/urls/update'", "'/urls/remove'",
                         'id="new-url-reason"', 'Motivo de la baja',
                         'Continúa el seguimiento manual fuera de la aplicación',
                         'historial_fuentes.md', 'se publica en GitHub'):
            self.assertIn(fragment, html)
        self.assertNotIn('saveUrls', html)

    def test_bulk_save_no_longer_exists(self):
        response = self.client.post('/urls', json={'urls': [URL_1]})
        self.assertEqual(response.status_code, 405)

    # -- fallos de guardado --------------------------------------------------

    def test_failure_preparing_drafts_changes_nothing(self):
        fuentes.ensure_history()
        before = self.snapshot()
        real_write = monitor._write_temp_text
        calls = {'count': 0}

        def failing_on_history(target, text):
            calls['count'] += 1
            if calls['count'] == 2:
                raise OSError('disco lleno simulado')
            return real_write(target, text)

        with patch.object(monitor, '_write_temp_text', side_effect=failing_on_history):
            response = self.post('/urls/add', url=URL_NUEVA, motivo='x')
        self.assert_rejected(response, 500, 'no se aplicó', before)

    def test_failure_recording_history_restores_previous_list(self):
        fuentes.ensure_history()
        before = self.snapshot()
        real_replace = os.replace

        def failing_on_history(src, dst):
            if Path(dst).name == 'historial_fuentes.md':
                raise OSError('historial bloqueado')
            return real_replace(src, dst)

        with patch.object(monitor._os, 'replace', side_effect=failing_on_history):
            response = self.post('/urls/add', url=URL_NUEVA, motivo='x')
        self.assert_rejected(response, 500, 'se restauró la lista anterior', before)


class ExternalChangesTests(SourcesTestBase):
    """Etapa 3: cambios en urls.txt hechos a mano o desde GitHub."""

    def check(self):
        response = self.client.get('/urls/external-changes')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def edit_urls_by_hand(self, urls):
        self.urls_file.write_text('\n'.join(urls) + '\n', encoding='utf-8')

    def test_external_no_differences_means_no_warning(self):
        data = self.check()  # crea el inventario inicial
        self.assertEqual(data, {'added': [], 'removed': [], 'pending': False})
        self.post('/urls/add', url=URL_NUEVA, motivo='Alta desde la app')
        self.post('/urls/update', url_anterior=URL_1, url='https://uno.example/v2', motivo='Mod')
        self.post('/urls/remove', url=URL_2, motivo='Baja desde la app')
        self.assertFalse(self.check()['pending'])

    def test_external_added_and_removed_sources_are_detected(self):
        self.check()
        self.edit_urls_by_hand([URL_1, URL_NUEVA])  # se quitó URL_2 y se agregó URL_NUEVA
        data = self.check()
        self.assertEqual(data['added'], [URL_NUEVA])
        self.assertEqual(data['removed'], [URL_2])
        self.assertTrue(data['pending'])

    def test_external_registration_records_reasons_without_touching_urls(self):
        self.check()
        self.edit_urls_by_hand([URL_1, URL_NUEVA])
        urls_before = self.urls_file.read_bytes()
        response = self.client.post('/urls/external-changes', json={'changes': [
            {'url': URL_NUEVA, 'tipo': 'alta', 'motivo': 'Agregada desde GitHub'},
            {'url': URL_2, 'tipo': 'baja', 'motivo': 'Quitada a mano'},
        ]})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(self.urls_file.read_bytes(), urls_before)
        text = self.history()
        self.assertIn('## 2026-11-16 09:20 · Alta (fuera de la aplicación)\n'
                      f'- URL: {URL_NUEVA}\n- Motivo: Agregada desde GitHub\n', text)
        self.assertIn('## 2026-11-16 09:20 · Baja (fuera de la aplicación)\n'
                      f'- URL: {URL_2}\n- Motivo: Quitada a mano\n', text)
        self.assertFalse(self.check()['pending'])

    def test_external_registration_requires_every_reason(self):
        self.check()
        self.edit_urls_by_hand([URL_1, URL_2, URL_NUEVA])
        before = self.snapshot()
        response = self.client.post('/urls/external-changes', json={'changes': [
            {'url': URL_NUEVA, 'tipo': 'alta', 'motivo': ''},
        ]})
        self.assert_rejected(response, 400, 'motivo', before)

    def test_external_registration_rejects_outdated_list(self):
        self.check()
        self.edit_urls_by_hand([URL_1, URL_2, URL_NUEVA])
        # Mientras el aviso estaba abierto, el archivo volvió a cambiar.
        self.edit_urls_by_hand([URL_1, URL_2, URL_NUEVA, 'https://otra.example/'])
        before = self.snapshot()
        response = self.client.post('/urls/external-changes', json={'changes': [
            {'url': URL_NUEVA, 'tipo': 'alta', 'motivo': 'x'},
        ]})
        self.assert_rejected(response, 400, 'cambió', before)

    def test_external_registration_allowed_during_a_run(self):
        self.check()
        self.edit_urls_by_hand([URL_1, URL_2, URL_NUEVA])
        with app_module._state_lock:
            app_module._state['running'] = True
        try:
            response = self.client.post('/urls/external-changes', json={'changes': [
                {'url': URL_NUEVA, 'tipo': 'alta', 'motivo': 'x'}]})
        finally:
            with app_module._state_lock:
                app_module._state['running'] = False
        self.assertEqual(response.status_code, 200)

    def test_external_manual_edit_of_a_url_appears_as_removal_plus_addition(self):
        self.check()
        self.edit_urls_by_hand(['https://uno.example/nueva-ruta', URL_2])
        data = self.check()
        self.assertEqual(data['added'], ['https://uno.example/nueva-ruta'])
        self.assertEqual(data['removed'], [URL_1])

    def test_external_unreadable_history_is_reported_not_hidden(self):
        self.check()
        with open(self.history_file, 'a', encoding='utf-8') as handle:
            handle.write('\n## 2026-11-16 10:00 · Acción inventada\n- URL: https://x.example\n')
        response = self.client.get('/urls/external-changes')
        self.assertEqual(response.status_code, 500)
        self.assertIn('Acción inventada', response.get_json()['error'])

    def test_external_replay_handles_every_action(self):
        text = '\n'.join([
            '## 2026-11-01 08:00 · Inventario inicial',
            '- Fuentes (2):', f'  - {URL_1}', f'  - {URL_2}',
            '## 2026-11-02 08:00 · Alta', f'- URL: {URL_NUEVA}', '- Motivo: a',
            '## 2026-11-03 08:00 · Modificación', '- URL: https://uno.example/v2',
            f'- URL anterior: {URL_1}', '- Motivo: b',
            '## 2026-11-04 08:00 · Baja (fuera de la aplicación)', f'- URL: {URL_2}', '- Motivo: c',
        ])
        self.assertEqual(fuentes.expected_urls_from_history(text),
                         ['https://uno.example/v2', URL_NUEVA])

    def test_external_page_contains_warning(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('id="external-changes"', html)
        self.assertIn('checkExternalChanges()', html)


if __name__ == '__main__':
    unittest.main()
