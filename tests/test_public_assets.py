import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import public_assets
from _public_fixture import make_sealed_fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deployment_boundary', ROOT / 'deploy.py')
deployment = importlib.util.module_from_spec(spec); spec.loader.exec_module(deployment)


class PublicAssetBoundaryTests(unittest.TestCase):
    def test_missing_registered_root_asset_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_sealed_fixture(root)
            rules = json.loads((root / 'public.assets').read_text()); rules['root_files'].append('app.js')
            (root / 'public.assets').write_text(json.dumps(rules))
            with self.assertRaisesRegex(ValueError, 'Missing required public root'): public_assets.seal(root)

    def test_private_build_input_changes_invalidate_receipt_without_uploading_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_sealed_fixture(root)
            (root / 'repos.json').write_text('{"fixture":1}'); public_assets.seal(root)
            self.assertNotIn('repos.json', public_assets.collect_public_files(root))
            (root / 'repos.json').write_text('{"fixture":2}')
            with self.assertRaisesRegex(ValueError, 'stale'): public_assets.collect_public_files(root)

    def test_private_python_input_symlink_cannot_be_fingerprinted(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory); make_sealed_fixture(root)
            path = Path(outside) / 'fixture.py'; path.write_text('# harmless fixture')
            (root / 'build_data.py').symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'symlink'): public_assets.seal(root)

    def test_private_account_patch_browser_and_log_files_are_never_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_sealed_fixture(root)
            for name in ['evidence/gsc.json', 'account/browser.html', 'patches/manifest.json', 'tests/private.js',
                         '.build-assets/private.json', 'verification/log.txt', 'report.json', 'manifest.json', 'gsc.txt', 'session.html', 'repos.json']:
                target = root / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('private synthetic fixture')
            public_assets.seal(root)
            self.assertEqual(public_assets.collect_public_files(root), ['index.html'])

    def test_unknown_root_files_cannot_be_added_to_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_sealed_fixture(root)
            rules = json.loads((root / 'public.assets').read_text()); rules['root_files'].append('account.json')
            (root / 'public.assets').write_text(json.dumps(rules))
            with self.assertRaisesRegex(ValueError, 'Unapproved public root'): public_assets.planned_files(root)

    def test_symlink_ancestors_and_root_assets_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory); make_sealed_fixture(root)
            (root / 'index.html').unlink(); (root / 'index.html').symlink_to(Path(outside) / 'secret')
            with self.assertRaisesRegex(ValueError, 'symlink'): public_assets.planned_files(root)
            (root / 'index.html').unlink(); (root / 'index.html').write_text('public')
            (root / 'p').symlink_to(outside, target_is_directory=True)
            (root / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://fixture.invalid/p/entity/</loc></url></urlset>')
            with self.assertRaisesRegex(ValueError, 'symlink'): public_assets.planned_files(root)

    def test_stale_build_and_cross_host_sitemap_fail_before_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_sealed_fixture(root); (root / 'index.html').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'stale'): public_assets.collect_public_files(root)
            with patch.object(deployment, 'ROOT', directory), patch.object(deployment, 'TOKEN', 'fixture'), patch.object(deployment, 'req') as request:
                with self.assertRaises(ValueError): deployment.main()
                request.assert_not_called()
            (root / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://other.invalid/</loc></url></urlset>')
            with self.assertRaisesRegex(ValueError, 'same-host'): public_assets.planned_files(root)

    def test_new_current_entity_is_selected_only_through_sitemap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_sealed_fixture(root)
            target = root / 'p/entity/index.html'; target.parent.mkdir(parents=True); target.write_text('public entity')
            self.assertNotIn('p/entity/index.html', public_assets.planned_files(root))
            (root / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://fixture.invalid/</loc></url><url><loc>https://fixture.invalid/p/entity/</loc></url></urlset>')
            self.assertIn('p/entity/index.html', public_assets.seal(root)['public_files'])

    def test_target_override_and_wrong_returned_id_cannot_bypass_binding(self):
        with patch.object(deployment, 'PROJECT', 'wrong-target'), patch.dict('os.environ', {'ALLOW_OVERWRITE': '1'}), patch.object(deployment, 'req') as request:
            with self.assertRaises(SystemExit): deployment._preflight_overwrite_guard()
            request.assert_not_called()
        with patch.object(deployment, 'PROJECT', deployment.EXPECTED_PROJECT_NAME), patch.dict('os.environ', {'ALLOW_OVERWRITE': '1'}), patch.object(deployment, 'req', return_value=(200, b'{"id":"wrong-project"}')) as request:
            with self.assertRaises(SystemExit): deployment._preflight_overwrite_guard()
            self.assertEqual(request.call_count, 1)
            self.assertNotIn('method', request.call_args.kwargs)

    def test_rejected_upload_never_creates_a_partial_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); make_sealed_fixture(root)
            with patch.object(deployment, 'ROOT', directory), patch.object(deployment, 'TOKEN', 'fixture'), patch.object(deployment, '_preflight_overwrite_guard'), patch.object(deployment, 'req', return_value=(403, b'fixture denial')) as request:
                self.assertEqual(deployment.main(), 1)
                self.assertEqual(request.call_count, 1)
                self.assertIn('/v2/files', request.call_args.args[0])

    def test_actual_public_inventory_preserves_required_assets_without_private_inputs(self):
        selected = public_assets.planned_files(ROOT)
        for path in ('index.html', 'data.json', 'app.js', 'guidance.js', 'sitemap.xml', 'robots.txt', 'llms.txt', 'ai.txt'):
            self.assertIn(path, selected)
        for path in selected:
            self.assertFalse(path.startswith(('tests/', 'evidence/', 'patches/', '.build-assets/', 'account/')))
            self.assertNotIn(path, ('repos.json', 'public.build', 'public.assets', 'selection.guide', 'url.lifecycle', 'inclusion.policy'))
        if (ROOT / 'vercel.json').exists(): self.assertIn('vercel.json', selected)


if __name__ == '__main__': unittest.main()
