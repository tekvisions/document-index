#!/usr/bin/env python3
"""Record retention decisions for published routes that left the discovery window.

Runs before ``url_lifecycle.py --render-retained``. For each protected URL that is
not in the regenerated sitemap and has no recorded decision (retained reference,
retirement or alias), it reads the route's record from the last committed catalog
(``git show HEAD:data.json``) and checks the publisher source:

* source reachable: append a dated, unranked ``retained_references`` entry built
  only from that saved catalog record and the publisher README/model card, with
  the check date, HTTP status and evidence sha256;
* source answers 404/410/451 (Hugging Face also 401): append an honest "source
  unavailable" entry backed by a Wayback Machine copy when one exists;
* anything else (no saved record, no Wayback copy, rate limit, timeout): no
  decision, so ``url_lifecycle.py --verify`` still blocks the release.

The verify gate, the protected URL lists and all earlier decisions are untouched:
this only appends to ``retained_references``.
"""
import base64
import concurrent.futures as cf
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
UNAVAILABLE = {404, 410, 451}
# A discovery outage must not turn the whole catalog into references.
MAX_PENDING_SHARE = 0.5
UNC = re.compile(r'uncensor|abliterat|obliterat', re.I)
CJK = re.compile(r'[\u3000-\u9fff\uac00-\ud7af\uff00-\uffef]')


def fetch(url, headers=None):
    request = urllib.request.Request(url, headers={'User-Agent': 'kymata-index-auto-retain', **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status, response.read(5_000_000)
    except urllib.error.HTTPError as error:
        return error.code, b''
    except Exception:
        return 0, b''


def github_headers():
    token = os.environ.get('GITHUB_TOKEN')
    return {'Accept': 'application/vnd.github+json', **({'Authorization': 'Bearer ' + token} if token else {})}


def check_github(full_name, get=fetch):
    status, body = get('https://api.github.com/repos/' + full_name, github_headers())
    result = {'requested': full_name, 'http_status': status}
    if status != 200:
        return result
    repo = json.loads(body)
    result.update(available=True, full_name=repo['full_name'], html_url=repo['html_url'], archived=bool(repo.get('archived')), description=repo.get('description'))
    status, body = get('https://api.github.com/repos/' + repo['full_name'] + '/readme', github_headers())
    if status == 200:
        readme = json.loads(body)
        raw = base64.b64decode(readme['content']) if readme.get('encoding') == 'base64' else None
        if raw is not None:
            result.update(source_url=readme['html_url'], source_title='Publisher README', evidence_sha256=hashlib.sha256(raw).hexdigest(), blob_sha=readme['sha'])
    if 'evidence_sha256' not in result:
        meta = {k: repo.get(k) for k in ('full_name', 'html_url', 'description', 'archived', 'default_branch', 'pushed_at')}
        result.update(source_url=repo['html_url'], source_title='Publisher repository metadata (no README)', evidence_sha256=hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest())
    return result


def check_hf(model_id, get=fetch):
    status, body = get('https://huggingface.co/api/models/' + model_id)
    result = {'requested': model_id, 'http_status': status}
    if status != 200:
        return result
    model = json.loads(body)
    url = 'https://huggingface.co/' + model['id']
    result.update(available=True, full_name=model['id'], html_url=url, gated=bool(model.get('gated')), pipeline_tag=model.get('pipeline_tag'))
    status, card = get(url + '/raw/main/README.md')
    if status == 200:
        result.update(source_url=url, source_title='Publisher model card', evidence_sha256=hashlib.sha256(card).hexdigest())
    else:
        result.update(source_url=url, source_title='Publisher model page metadata (gated card)', evidence_sha256=hashlib.sha256(body).hexdigest())
    return result


def wayback(url, get=fetch):
    status, body = get('https://archive.org/wayback/available?url=' + urllib.parse.quote(url, safe=''))
    if status != 200:
        return None
    closest = (json.loads(body).get('archived_snapshots') or {}).get('closest') or {}
    if not closest.get('available') or str(closest.get('status')) != '200' or not re.fullmatch(r'\d{14}', str(closest.get('timestamp', ''))):
        return None
    snapshot = closest['url'].replace('http://', 'https://', 1)
    status, page = get(snapshot)
    if status != 200 or not page:
        return None
    return {'url': snapshot, 'timestamp': closest['timestamp'], 'evidence_sha256': hashlib.sha256(page).hexdigest()}


def sitemap_urls(root):
    return {node.text for node in ET.parse(Path(root) / 'sitemap.xml').getroot().iter(NS + 'loc')}


def pending_urls(root, rules):
    """Protected detail URLs that would reach url_lifecycle --verify with no decision."""
    protected = set(rules['captured_public_urls']) | set(rules.get('planned_release_urls', []))
    decided = {e['canonical_url'] for key in ('retained_references', 'retirements', 'aliases') for e in rules.get(key, [])}
    route = re.compile('https://' + re.escape(rules['host']) + '/' + re.escape(rules.get('detail_prefix', 'p')) + r'/[a-z0-9-]+/')
    return sorted(u for u in protected - sitemap_urls(root) - decided if route.fullmatch(u))


def slug_of(row):
    if row.get('slug'):
        return row['slug']
    if row.get('owner') and row.get('name'):  # stacktracker rows mirror gen_details.slugify()
        return re.sub(r'[^a-z0-9]+', '-', (row['owner'] + '-' + row['name']).lower()).strip('-')
    return None


def committed_catalog(root):
    """Rows of the last committed (published) data.json, its snapshot time and commit."""
    run = lambda *args: subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, timeout=60)
    shown = run('show', 'HEAD:data.json')
    if shown.returncode:
        return {}, None, None
    data = json.loads(shown.stdout)
    commit = run('log', '-1', '--format=%H', '--', 'data.json').stdout.strip() or run('rev-parse', 'HEAD').stdout.strip()
    rows = {slug_of(row): row for key in ('items', 'repos', 'models', 'servers') for row in data.get(key, []) if isinstance(row, dict) and slug_of(row)}
    return rows, data.get('generated_at'), commit


def clean(text):
    text = ' '.join((text or '').split()).replace(' — ', ', ').replace('—', ', ')
    text = re.sub(r'(,\s*)+,', ',', text).strip()
    return text if not text or text[-1] in '.!?' else text + '.'


def entry_for(canonical, row, check, snapshot, commit, today, is_model, supports_historical, archive=None):
    slug = canonical.rstrip('/').rsplit('/', 1)[1]
    entity = row.get('full_name') or row.get('id') or row.get('repo')
    category = row.get('category') or 'its saved category'
    host = 'Hugging Face' if is_model else 'GitHub'
    previous = ('https://huggingface.co/' if is_model else 'https://github.com/') + entity
    raw_description = row.get('description') or row.get('blurb') or ''
    description = '' if CJK.search(raw_description) else clean(raw_description)
    entry = {'slug': slug, 'entity': entity, 'canonical_url': canonical}
    if check.get('available'):
        repository = check['html_url']
        if is_model:
            task = (row.get('task') or check.get('pipeline_tag') or 'machine-learning').replace('-', ' ')
            summary = (f'{entity} is a Hugging Face model repository published by {row.get("author") or entity.split("/")[0]} and tagged for {task}. '
                       f'The saved {snapshot[:10]} catalog classified it under {category}' + (f' with the {row["license"]} license.' if row.get('license') else '.'))
            selection = f'Use this dated reference to find the publisher model card for {task} work, then compare it with the current ranked models before choosing a checkpoint.'
            limits = ('Automated dated publisher model-card check, not an independent quality, safety, licensing or hardware test. No current rank or trending score is assigned. '
                      'Verify the current model card, license, intended use and hardware requirements.')
            if UNC.search(entity):
                limits += ' The model name indicates that safety tuning was removed or altered; review the publisher terms and the risks of that change before any use.'
            if check.get('gated'):
                limits += ' The publisher gates the model files behind an access agreement.'
        else:
            if description:
                summary = f'Publisher description of {entity}: {description} The saved {snapshot[:10]} catalog classified it under {category}.'
            elif raw_description:
                summary = f'The saved {snapshot[:10]} catalog classified {entity} under {category}; the publisher description is not in English, so see the README for scope.'
            else:
                summary = f'The saved {snapshot[:10]} catalog classified {entity} under {category}; the publisher left the repository description blank, so see the README for scope.'
            selection = f'Use this dated reference to locate the publisher documentation for {category} work, then compare it with the current ranked catalog before choosing a tool.'
            limits = ('Automated dated publisher-documentation check, not an independent runtime, security or performance test. No current rank or momentum score is assigned. '
                      'Verify current availability, license and requirements.')
            if check.get('archived'):
                limits += ' The publisher has archived the repository, so it is read-only and no longer maintained there.'
        if check['full_name'].lower() != entity.lower():
            limits += f' {host} now resolves {entity} to {check["full_name"]}. Confirm the current scope under that name.'
            entry['previous_repository'] = previous
        source = {'url': check['source_url'], 'title': check['source_title'], 'evidence_sha256': check['evidence_sha256']}
        if check.get('blob_sha'):
            source['blob_sha'] = check['blob_sha']
        decision = 'Retain the published route as a dated unranked reference when absent from the current discovery snapshot.'
        upstream = f'publisher source reachable (HTTP {check["http_status"]}) on the {today} automated check'
    else:
        repository = previous
        stamp = archive['timestamp']
        captured = datetime.date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
        recorded = f' and recorded the publisher description: {description}' if description else '.'
        summary = (f'The saved {snapshot[:10]} catalog classified {entity} under {category}{recorded} '
                   f'The publisher {"model" if is_model else "repository"} returned HTTP {check["http_status"]} on the {host} API during the {today} check; '
                   'that does not establish whether it was deleted, renamed without a redirect or made private.')
        selection = 'Use this dated reference to trace the previously indexed project and its historical catalog classification; choose a currently available alternative from the ranked catalog.'
        limits = (f'The publisher source is currently unavailable, so this reference relies on an archived copy of its page from {captured.strftime("%B %Y")}. '
                  'Current documentation, installation, licensing and maintenance could not be verified. No current rank or momentum score is assigned, and no runtime test or benchmark is claimed.')
        source = {'url': archive['url'], 'title': f'Archived publisher page (Wayback Machine capture {captured.isoformat()})', 'evidence_sha256': archive['evidence_sha256']}
        decision = 'Preserve the existing published URL as a dated historical reference while the publisher source is unavailable.'
        upstream = f'publisher source unavailable (HTTP {check["http_status"]}) on the {today} automated check; archived copy used'
        if supports_historical:
            entry.update(source_status='historical_unavailable', schema_type='CreativeWork')
    entry.update(repository=repository, summary=summary, selection_context=selection, limitations=limits,
                 last_catalog_snapshot=snapshot, reviewed_on=today, last_successful_source_commit=commit,
                 decision=decision, upstream_status=upstream, primary_sources=[source], evidence_sha256=source['evidence_sha256'])
    return entry


def run(root=ROOT, today=None, get=fetch, catalog=None):
    root = Path(root)
    path = root / 'url.lifecycle'
    original = path.read_text(encoding='utf-8')
    rules = json.loads(original)
    today = today or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    pending = pending_urls(root, rules)
    report = {'pending': pending, 'retained': [], 'unavailable_archived': [], 'undecided': {}}
    if not pending:
        return report
    detail = [u for u in set(rules['captured_public_urls']) | set(rules.get('planned_release_urls', [])) if u.count('/') > 3]
    if len(pending) > MAX_PENDING_SHARE * max(1, len(detail)):
        report['undecided'] = {u: 'too many published routes left discovery at once; needs review' for u in pending}
        return report
    rows, snapshot, commit = catalog if catalog is not None else committed_catalog(root)
    is_model = rules.get('detail_prefix') == 'm'
    supports_historical = 'historical_unavailable' in (ROOT / 'url_lifecycle.py').read_text(encoding='utf-8')
    work = {}
    for canonical in pending:
        row = rows.get(canonical.rstrip('/').rsplit('/', 1)[1])
        entity = row and (row.get('full_name') or row.get('id') or row.get('repo'))
        if not row or not snapshot or not entity or not re.fullmatch(r'[\w.-]+/[\w.-]+', entity) or '..' in entity:
            report['undecided'][canonical] = 'no saved catalog record'
        else:
            work[canonical] = (row, entity)
    checker = check_hf if is_model else check_github
    with cf.ThreadPoolExecutor(8) as pool:
        checks = dict(zip(work, pool.map(lambda item: checker(item[1], get), work.values())))
    added = []
    for canonical, (row, entity) in work.items():
        check = checks[canonical]
        archive = None
        if not check.get('available'):
            gone = check['http_status'] in UNAVAILABLE or (is_model and check['http_status'] == 401)
            archive = wayback(('huggingface.co/' if is_model else 'github.com/') + entity, get) if gone else None
            if not archive:
                report['undecided'][canonical] = f'source HTTP {check["http_status"]}' + (' with no archived copy' if gone else '; retry later')
                continue
            report['unavailable_archived'].append(canonical)
        else:
            report['retained'].append(canonical)
        added.append(entry_for(canonical, row, check, snapshot, commit, today, is_model, supports_historical, archive))
    if added:
        rules['retained_references'] = rules.get('retained_references', []) + added
        indent = 2 if '\n  "' in original[:200] else 1
        path.write_text(json.dumps(rules, indent=indent, ensure_ascii=False) + ('\n' if original.endswith('\n') else ''), encoding='utf-8')
    return report


if __name__ == '__main__':
    result = run()
    print(json.dumps({k: (len(v) if k == 'pending' else v) for k, v in result.items()}, indent=1, sort_keys=True))
