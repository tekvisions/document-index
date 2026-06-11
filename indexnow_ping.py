#!/usr/bin/env python3
"""Ping IndexNow with every URL in this site's sitemap.xml.

Dropped into each Living Index repo and run as the final step of the daily GitHub
Action (after deploy.py) so every refresh re-submits the fleet to Bing/Yandex/Seznam/Naver.
Self-contained (stdlib only). Reads ./sitemap.xml, derives the host from its first <loc>,
and POSTs the URL list. Retries 403/429 (api.indexnow.org rate-limits rapid submissions).

Exit 0 always (best-effort; never fail a deploy on a submission hiccup).
"""
import json, os, re, sys, time, urllib.request, urllib.error

KEY = "061be3a140873a0279322a63c48f10ef"
ROOT = os.path.dirname(os.path.abspath(__file__))


def post(host, urls):
    payload = json.dumps({"host": host, "key": KEY,
        "keyLocation": f"https://{host}/{KEY}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=payload,
        headers={"Content-Type": "application/json; charset=utf-8", "User-agent": "kymata-indexnow/1.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR:{type(e).__name__}"


def main():
    sm = os.path.join(ROOT, "sitemap.xml")
    if not os.path.exists(sm):
        print("indexnow: no sitemap.xml, skipping"); return
    body = open(sm, encoding="utf-8").read()
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
    if not locs:
        print("indexnow: no <loc> entries, skipping"); return
    host = re.sub(r"^https?://", "", locs[0]).split("/")[0]
    urls = [u for u in locs if u.startswith(f"https://{host}")]
    for attempt in range(4):
        st = post(host, urls)
        if st in (200, 202):
            print(f"indexnow: {host} submitted {len(urls)} urls -> {st}"); return
        print(f"indexnow: {host} -> {st} (attempt {attempt + 1}); backing off")
        time.sleep(10 * (attempt + 1))
    print(f"indexnow: {host} gave up after retries (last={st})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never fail the deploy
        print(f"indexnow: error {e}", file=sys.stderr)
    sys.exit(0)
