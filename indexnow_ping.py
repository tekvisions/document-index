#!/usr/bin/env python3
"""Submit this site's sitemap after deployment, with explicit receipt semantics.

200 means received; 202 means received pending key validation. Neither establishes
indexing, ranking or delivery to every search engine. Failed submissions return a
nonzero status. This module performs no requests when imported.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

KEY = "061be3a140873a0279322a63c48f10ef"
ROOT = os.path.dirname(os.path.abspath(__file__))



class ProviderStatus(int):
    def __new__(cls,code,headers=None):
        value=int.__new__(cls,code)
        pairs=list(headers.items()) if headers else []
        value.retry_after=next((str(v)[:256] for k,v in pairs if str(k).lower()=='retry-after'),None)
        return value


def post(host, urls):
    payload = json.dumps({'host': host, 'key': KEY,
                          'keyLocation': f'https://{host}/{KEY}.txt', 'urlList': urls}).encode()
    request = urllib.request.Request('https://api.indexnow.org/indexnow', data=payload,
                                    headers={'Content-Type': 'application/json; charset=utf-8',
                                             'User-agent': 'kymata-indexnow/1.1'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return ProviderStatus(response.status,response.headers)
    except urllib.error.HTTPError as error:
        return ProviderStatus(error.code,error.headers)
    except Exception as error:
        # Do not log raw diagnostics, request payloads or credential-bearing URLs.
        return f'ERR:{type(error).__name__}'


def receipt(host, urls, status, attempt):
    outcome = 'received' if status == 200 else 'received_pending_key_validation' if status == 202 else 'failed'
    print(json.dumps({'event': 'indexnow_submission', 'observed_at': datetime.now(timezone.utc).isoformat(),
                      'host': host, 'url_count': len(urls), 'http_status': status,
                      'attempt': attempt, 'outcome': outcome, 'retry_after': getattr(status,'retry_after',None)}, sort_keys=True))


def main():
    path = os.path.join(ROOT, 'sitemap.xml')
    tree = ET.parse(path)
    urls = list(dict.fromkeys(node.text.strip() for node in tree.getroot().iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc') if node.text))
    if not urls:
        raise ValueError('Sitemap has no URLs')
    host = urlparse(urls[0]).netloc
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != host or parsed.username or parsed.password:
            raise ValueError('Sitemap must contain HTTPS URLs for exactly one host')
    if len(urls) > 10000:
        raise ValueError('Sitemap exceeds the IndexNow single-request limit')
    keyfile = os.path.join(ROOT, KEY + '.txt')
    with open(keyfile, encoding='utf-8') as stream:
        if stream.read().strip() != KEY:
            raise ValueError('Published key file does not match the configured key')
    for attempt in range(1, 5):
        status = post(host, urls)
        receipt(host, urls, status, attempt)
        if status in (200, 202):
            return 0
        retry = (not isinstance(status, int) or status >= 500) and getattr(status,'retry_after',None) is None
        if not retry or attempt == 4:
            return 1
        time.sleep(min(10 * attempt, 30))
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'indexnow: failed ({type(error).__name__}); no successful receipt', file=sys.stderr)
        sys.exit(1)
