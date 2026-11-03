import contextlib,io,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import indexnow_ping as indexnow

class ProviderBackoffTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        root=Path(self.folder.name)
        (root/'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://mcp.kymatalabs.com/</loc></url></urlset>')
        (root/(indexnow.KEY+'.txt')).write_text(indexnow.KEY)
        patched=patch.object(indexnow,'ROOT',str(root));patched.start();self.addCleanup(patched.stop)

    def test_retry_after_and_rate_limit_stop_without_sleep_or_second_request(self):
        for status in (indexnow.ProviderStatus(503,{'Retry-After':'120'}),indexnow.ProviderStatus(429)):
            with self.subTest(status=int(status)),patch.object(indexnow,'post',return_value=status) as post,patch.object(indexnow.time,'sleep') as sleep,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(indexnow.main(),1)
                self.assertEqual(post.call_count,1);sleep.assert_not_called()

    def test_successful_final_batch_honors_retry_after_without_followup(self):
        with patch.object(indexnow,'post',return_value=indexnow.ProviderStatus(200,{'Retry-After':'120'})) as post,patch.object(indexnow.time,'sleep') as sleep,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(indexnow.main(),0)
            self.assertEqual(post.call_count,1);sleep.assert_not_called()

if __name__=='__main__':unittest.main()
