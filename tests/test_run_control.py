import asyncio
import threading
import time
import unittest
from unittest.mock import patch

import app as app_module
import monitor


class ProcessUrlControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_playwright_context_manager_is_closed(self):
        class FakeBrowser:
            async def close(self):
                pass

        class FakeChromium:
            async def launch(self, **kwargs):
                return FakeBrowser()

        class FakePlaywright:
            chromium = FakeChromium()

        class FakePlaywrightManager:
            def __init__(self):
                self.exited = False

            async def __aenter__(self):
                return FakePlaywright()

            async def __aexit__(self, exc_type, exc, traceback):
                self.exited = True

        manager = FakePlaywrightManager()

        async def fake_fetch_url(session, url, browser=None):
            return url, 'Success', 'contenido verificable', ''

        with (
            patch.object(monitor, 'async_playwright', return_value=manager),
            patch.object(monitor, 'fetch_url', new=fake_fetch_url),
        ):
            results = await monitor.process_urls(['https://ok.example'])

        self.assertEqual(results[0][1], 'Success')
        self.assertTrue(manager.exited)

    async def test_timeout_marks_source_and_continues(self):
        async def fake_fetch_url(session, url, browser=None):
            if url == 'https://slow.example':
                await asyncio.sleep(1)
            return url, 'Success', 'contenido verificable', ''

        with (
            patch.object(monitor, 'async_playwright', None),
            patch.object(monitor, 'fetch_url', new=fake_fetch_url),
        ):
            results = await monitor.process_urls(
                ['https://slow.example', 'https://ok.example'],
                per_url_timeout=0.02,
            )

        self.assertEqual(results[0][1], 'Error')
        self.assertIn('revisión manual', results[0][3])
        self.assertEqual(results[1][1], 'Success')
        self.assertEqual(results[1][0], 'https://ok.example')

    async def test_cancel_interrupts_the_current_source(self):
        cancel_event = threading.Event()

        async def fake_fetch_url(session, url, browser=None):
            await asyncio.sleep(1)
            return url, 'Success', 'contenido verificable', ''

        asyncio.get_running_loop().call_later(0.02, cancel_event.set)
        with (
            patch.object(monitor, 'async_playwright', None),
            patch.object(monitor, 'fetch_url', new=fake_fetch_url),
        ):
            with self.assertRaises(monitor.RunCancelled):
                await monitor.process_urls(
                    ['https://slow.example'],
                    should_cancel=cancel_event.is_set,
                    per_url_timeout=1,
                )

    async def test_unexpected_source_error_does_not_stop_the_batch(self):
        async def fake_fetch_url(session, url, browser=None):
            if url == 'https://broken.example':
                raise RuntimeError('fallo simulado')
            return url, 'Success', 'contenido verificable', ''

        with (
            patch.object(monitor, 'async_playwright', None),
            patch.object(monitor, 'fetch_url', new=fake_fetch_url),
        ):
            results = await monitor.process_urls(
                ['https://broken.example', 'https://ok.example'],
                per_url_timeout=1,
            )

        self.assertEqual(results[0][1], 'Error')
        self.assertIn('fallo simulado', results[0][3])
        self.assertEqual(results[1][1], 'Success')



class PersistenceTests(unittest.TestCase):
    def test_cancelled_run_does_not_overwrite_previous_results(self):
        async def cancelled_process(*args, **kwargs):
            raise monitor.RunCancelled()

        with (
            patch.object(monitor, 'load_urls', return_value=['https://slow.example']),
            patch.object(monitor, 'load_hashes', return_value={'anterior': 'hash'}),
            patch.object(monitor, 'load_metadata', return_value={'anterior': {}}),
            patch.object(monitor, 'process_urls', new=cancelled_process),
            patch.object(monitor, 'save_run_outputs') as save_run_outputs,
        ):
            with self.assertRaises(monitor.RunCancelled):
                monitor.run_monitor()

        save_run_outputs.assert_not_called()

class RunApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        # Estas pruebas no dependen de la hora de la última corrida real.
        no_previous_run = patch.object(app_module, 'get_last_completed_at', return_value=None)
        no_previous_run.start()
        self.addCleanup(no_previous_run.stop)
        app_module._cancel_event.clear()
        with app_module._state_lock:
            app_module._state.update({
                'running': False,
                'cancel_requested': False,
                'run_state': 'idle',
                'message': '',
                'current': 0,
                'total': 0,
                'url': '',
                'playwright_available': None,
                'playwright_message': '',
                'started_at': '',
                'last_progress_at': '',
                'finished_at': '',
            })

    def test_cancel_endpoint_and_duplicate_run_protection(self):
        worker_started = threading.Event()

        def fake_run_monitor(on_progress, on_playwright_status, should_cancel):
            on_progress(0, 1, 'https://slow.example')
            worker_started.set()
            while not should_cancel():
                time.sleep(0.005)
            raise monitor.RunCancelled()

        with (
            patch.object(app_module, 'load_urls', return_value=['https://slow.example']),
            patch.object(app_module, 'run_monitor', side_effect=fake_run_monitor),
        ):
            response = self.client.post('/run')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(worker_started.wait(timeout=1))

            duplicate = self.client.post('/run')
            self.assertEqual(duplicate.status_code, 409)

            cancelled = self.client.post('/cancel')
            self.assertEqual(cancelled.status_code, 202)

            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                status = self.client.get('/status').get_json()
                if not status['running']:
                    break
                time.sleep(0.01)

        self.assertFalse(status['running'])
        self.assertEqual(status['run_state'], 'cancelled')
        self.assertIn('resultados anteriores', status['message'])

    def test_cancel_without_active_run_returns_conflict(self):
        response = self.client.post('/cancel')
        self.assertEqual(response.status_code, 409)

    def test_page_contains_recovery_and_manual_review_controls(self):
        html = self.client.get('/').get_data(as_text=True)
        self.assertIn('id="btn-cancel"', html)
        self.assertIn('No verificadas', html)
        self.assertIn('syncRunState()', html)
        self.assertIn('Revisar fuente', html)


if __name__ == '__main__':
    unittest.main()
