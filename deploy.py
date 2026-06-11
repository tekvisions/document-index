#!/usr/bin/env python3
"""Deploy this static directory to Vercel via the REST API.

Used both for manual ships and by the daily GitHub Action. Avoids the Vercel
CLI (which hangs in some headless/CC environments). Uploads each file by SHA,
then creates a production deployment.

Env:
  VERCEL_TOKEN   (required)
  VERCEL_TEAM_ID (default: techtalevisions-projects team)
  VERCEL_PROJECT (default: stacktracker)
"""
import hashlib, json, os, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN = os.environ.get("VERCEL_TOKEN", "").strip()
TEAM = os.environ.get("VERCEL_TEAM_ID", "team_L6hpqgg8pEHznOzrnU66JuoW").strip()
PROJECT = os.environ.get("VERCEL_PROJECT", "eval-index").strip()
SKIP = {".git", ".vercel", "node_modules", "__pycache__"}
SKIP_FILES = {".DS_Store"}
# only ship what the site needs — never the build scripts or workflow
INCLUDE_EXT = {".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".txt", ".xml"}


def req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()



def _preflight_overwrite_guard():
    """Refuse to clobber a project that already serves a REAL production site.

    This pipeline ships *static* sites (framework=None, no git ref). A real app
    (e.g. Next.js) has a framework and/or a git-linked production deployment.
    If we see one, abort — deploying static files would destroy it. This is the
    guard that would have prevented the 2026-06-01 kymatalabs clobber. Force with
    ALLOW_OVERWRITE=1.
    """
    if os.environ.get("ALLOW_OVERWRITE") == "1":
        return
    st, resp = req(f"https://api.vercel.com/v9/projects/{PROJECT}?teamId={TEAM}",
                   headers={"Authorization": f"Bearer {TOKEN}"})
    if st == 404:
        return  # project doesn't exist yet -> first deploy, nothing to overwrite
    if st >= 400:
        # cannot verify (401/403/5xx) -> FAIL CLOSED, don't risk a clobber
        print(f"REFUSING to deploy: could not verify project '{PROJECT}' "
              f"(HTTP {st}). Failing closed to protect any existing site. "
              f"Re-run with ALLOW_OVERWRITE=1 only if you intend to deploy anyway.",
              file=sys.stderr)
        sys.exit(2)
    try:
        proj = json.loads(resp)
    except Exception:
        print(f"REFUSING to deploy: project '{PROJECT}' response was unparseable; "
              f"failing closed. Re-run with ALLOW_OVERWRITE=1 to force.", file=sys.stderr)
        sys.exit(2)
    fw = proj.get("framework")
    prod = (proj.get("targets") or {}).get("production") or {}
    ref = (prod.get("meta") or {}).get("githubCommitRef")
    if fw or ref:
        sha = (prod.get("meta") or {}).get("githubCommitSha", "")[:10]
        print(
            f"REFUSING to deploy: project '{PROJECT}' already serves a real "
            f"production site (framework={fw!r}, prod git ref={ref!r} {sha}).\n"
            f"This pipeline ships static files and would DESTROY it. "
            f"Re-run with ALLOW_OVERWRITE=1 only if you truly intend to replace it.",
            file=sys.stderr,
        )
        sys.exit(2)


def main():
    if not TOKEN:
        print("VERCEL_TOKEN not set", file=sys.stderr)
        return 1
    _preflight_overwrite_guard()
    files = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            if f in SKIP_FILES:
                continue
            if os.path.splitext(f)[1].lower() not in INCLUDE_EXT:
                continue  # skip build_data.py / deploy.py / repos.json-adjacent tooling
            rel = os.path.relpath(os.path.join(dp, f), ROOT)
            files.append(rel)

    payload = []
    for rel in files:
        body = open(os.path.join(ROOT, rel), "rb").read()
        sha = hashlib.sha1(body).hexdigest()
        st, _ = req(f"https://api.vercel.com/v2/files?teamId={TEAM}", data=body,
                    headers={"Authorization": f"Bearer {TOKEN}",
                             "Content-Type": "application/octet-stream",
                             "x-vercel-digest": sha}, method="POST")
        print(f"  upload {rel}: {st}", file=sys.stderr)
        payload.append({"file": rel, "sha": sha, "size": len(body)})

    dep = {"name": PROJECT, "project": PROJECT, "target": "production", "files": payload,
           "projectSettings": {"framework": None, "buildCommand": None,
                               "installCommand": None, "outputDirectory": None}}
    st, resp = req(f"https://api.vercel.com/v13/deployments?teamId={TEAM}&forceNew=1",
                   data=json.dumps(dep).encode(),
                   headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                   method="POST")
    d = json.loads(resp)
    if st >= 400:
        print("deploy error:", json.dumps(d, indent=2)[:600], file=sys.stderr)
        return 1
    print(f"deployed: https://{d.get('url')}  state={d.get('readyState')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
