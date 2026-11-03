import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('indexnow', ROOT / 'indexnow_ping.py')
indexnow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indexnow)


class IndexNowReceiptTests(unittest.TestCase):
    def run_with(self, statuses):
        output = io.StringIO()
        with patch.object(indexnow, 'post', side_effect=statuses) as request, patch.object(indexnow.time, 'sleep') as sleep, contextlib.redirect_stdout(output):
            result = indexnow.main()
        return result, [json.loads(row) for row in output.getvalue().splitlines()], request.call_count, sleep.call_count

    def test_received_does_not_claim_indexing(self):
        code, rows, calls, _ = self.run_with([200])
        self.assertEqual(code, 0)
        self.assertEqual(rows[0]['outcome'], 'received')
        self.assertEqual(calls, 1)
        self.assertNotIn('indexed', json.dumps(rows))

    def test_202_is_pending_validation(self):
        code, rows, calls, _ = self.run_with([202])
        self.assertEqual(code, 0)
        self.assertEqual(rows[0]['outcome'], 'received_pending_key_validation')
        self.assertEqual(calls, 1)

    def test_persistent_failure_returns_nonzero(self):
        code, rows, calls, sleeps = self.run_with([503, 503, 503, 503])
        self.assertEqual(code, 1)
        self.assertEqual(calls, 4)
        self.assertEqual(sleeps, 3)
        self.assertTrue(all(row['outcome'] == 'failed' for row in rows))

    def test_bad_key_permission_and_bad_request_are_not_retried(self):
        for status in (400, 403, 422):
            code, rows, calls, sleeps = self.run_with([status])
            self.assertEqual((code, calls, sleeps), (1, 1, 0))

    def test_off_host_sitemap_is_rejected_without_a_request(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url><url><loc>https://example.com.evil.test/</loc></url></urlset>')
            with patch.object(indexnow, 'ROOT', folder), patch.object(indexnow, 'post') as request:
                with self.assertRaises(ValueError):
                    indexnow.main()
                request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
