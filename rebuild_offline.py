#!/usr/bin/env python3
"""Reconstruct this site's static outputs from existing data.json, with no fetch.

Run only in an isolated build directory: original generators prune their own
old outputs. Never invokes build_data.main(), deployment or search submissions.
"""
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def rebuild():
    data_path = ROOT / 'data.json'
    snapshot_bytes = data_path.read_bytes()
    data = json.loads(snapshot_bytes)
    robot_path = ROOT / 'robots.txt'
    original_robots = robot_path.read_bytes() if robot_path.exists() else None
    key = next((key for key in ('items', 'repos', 'models', 'servers', 'indexes') if data.get(key)), None)
    if not key or not data.get('generated_at'):
        raise ValueError('A nonempty, dated existing data.json snapshot is required')
    with patch('urllib.request.urlopen', side_effect=AssertionError('Offline reconstruction attempted a network request')):
        if key == 'items':
            import build_data
            import gen_details
            build_data.write_seo(data)
            gen_details.main()
        elif key == 'servers':
            import build_data
            build_data.generate_details(data, out_dir=str(ROOT))
        elif key == 'models':
            import build_data
            slugs = build_data.generate_details(data)
            build_data.write_sitemap(slugs, data.get('generated_date'))
        elif key == 'repos':
            if 'agentvelocity.' in (ROOT / 'home.template').read_text():
                import build_data
                build_data.generate_details(data)
            else:
                import gen_details
                gen_details.generate_details(data, here=str(ROOT))
        # The hub's snapshot already contains its sibling summaries; no fetch.
        elif key == 'indexes':
            from render_home import identity
            site, _ = identity((ROOT / 'home.template').read_text())
            (ROOT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>' + site + '</loc></url></urlset>\n')
        # Existing write_seo routines also write robots; preserve policy bytes.
        if original_robots is not None:
            robot_path.write_bytes(original_robots)
        import url_lifecycle
        url_lifecycle.render_retained(ROOT)
        import sanitize_detail_schema
        import render_home
        sanitize_detail_schema.sanitize(ROOT)
        render_home.render(ROOT)
        url_lifecycle.verify(ROOT)
        import public_assets
        public_assets.seal(ROOT)
    if data_path.read_bytes() != snapshot_bytes:
        raise AssertionError('Offline reconstruction unexpectedly changed source snapshot bytes')
    print('Offline reconstruction complete; snapshot unchanged; no network/deploy/submission')


if __name__ == '__main__':
    rebuild()
