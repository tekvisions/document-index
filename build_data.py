#!/usr/bin/env python3
"""The Document Index — recompute the living index of document-AI tooling from live GitHub
signals, and write data.json + SEO (sitemap, rss, robots, llms.txt).

Scope = the tools that turn documents into structured, LLM-ready data: OCR engines, PDF
extraction, document parsing, layout & structure analysis, table extraction, and
vision-language document understanding. NOT RAG orchestration (rag-index), NOT vector DBs,
NOT image generation (diffusion-index), NOT agents. Gathered, deduped, FILTERED (precision
over recall), categorized, scored.

Only the GitHub *search* payload is used. Env: GITHUB_TOKEN (required for a usable rate limit).
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.github.com"
SITE_URL = "https://document.kymatalabs.com"   # fixed to the real alias after first deploy
SITE_NAME = "The Document Index"

QUERIES = [
    "topic:ocr stars:>200",
    "topic:document-ai stars:>60",
    "topic:document-parsing stars:>50",
    "topic:document-understanding stars:>80",
    "topic:layout-analysis stars:>40",
    "topic:table-extraction stars:>40",
    "topic:pdf-extraction stars:>60",
    "topic:document-layout-analysis stars:>40",
    "topic:pdf stars:>500",
    "document parsing in:name,description stars:>120",
    "pdf to markdown in:name,description stars:>120",
    "document ai in:name,description stars:>150",
    "ocr in:name,description stars:>400",
    "table extraction in:name,description stars:>80",
    "document understanding in:name,description stars:>100",
    "pdf extraction in:name,description stars:>120",
    "layout analysis in:name,description stars:>80",
    "extract text from pdf in:name,description stars:>120",
]


def token() -> str:
    return (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()


HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "document-index"}
if token():
    HEADERS["Authorization"] = f"Bearer {token()}"

_DOC_TOPICS = {"ocr", "document-ai", "document-parsing", "document-understanding", "layout-analysis",
               "table-extraction", "pdf-extraction", "document-layout-analysis", "document-processing",
               "pdf-to-markdown", "optical-character-recognition", "text-extraction", "table-recognition",
               "document-image-analysis", "handwriting-recognition", "pdf-parser", "doctr", "donut",
               "information-extraction", "document-intelligence", "scanned-documents"}
_DOC_PHRASES = re.compile(
    r"\b(\bocr\b|optical character recognition|document (parsing|ai|understanding|intelligence|extraction|layout|processing)"
    r"|pdf (parser|extraction|to markdown|to text|to json|to html|processing)|extract (text|tables|data) from (pdf|document|image)"
    r"|table (extraction|recognition|detection)|layout (analysis|detection|parsing)|text extraction"
    r"|handwriting recognition|scanned (document|pdf)|parse (pdf|document)s?|markdown from (pdf|document)"
    r"|vision[- ]language.*document|document image|structured (data )?from (pdf|document))\b", re.I)

# RAG orchestration (rag-index), vector DBs, image gen (diffusion), general LLM/agent, office-suite
# clones, and libs that match but aren't document-EXTRACTION tooling.
_ALLOW = {
    "tesseract-ocr/tesseract", "paddlepaddle/paddleocr", "jaidedai/easyocr", "vikparuchuri/marker",
    "vikparuchuri/surya", "opendatalab/mineru", "unstructured-io/unstructured", "docling-project/docling",
    "ds4sd/docling", "mindee/doctr", "allenai/olmocr", "getomni-ai/zerox", "facebookresearch/nougat",
    "layout-parser/layout-parser", "ocrmypdf/ocrmypdf", "pymupdf/pymupdf", "jsvine/pdfplumber",
    "atlanhq/camelot", "camelot-dev/camelot", "vsakkas/img2table", "clovaai/donut",
    "deepdoctection/deepdoctection", "kermitt2/grobid", "ucbepic/docetl", "0xobelisk/getomni",
    "breezedeus/pix2text", "rapidai/rapidocr", "huridocs/pdf-document-layout-analysis",
    "py-pdf/pypdf", "datalab-to/marker", "datalab-to/surya",
}
_DENY = {
    "langchain-ai/langchain", "run-llama/llama_index", "langgenius/dify", "infiniflow/ragflow",
    "chroma-core/chroma", "imartinez/privategpt", "vllm-project/vllm", "ollama/ollama",
    "open-webui/open-webui", "huggingface/transformers", "huggingface/diffusers", "microsoft/markitdown",
    "danny-avila/librechat", "lobehub/lobe-chat", "facebookresearch/detectron2", "open-mmlab/mmdetection",
    "ultralytics/ultralytics", "jofpin/trape", "qpdf/qpdf", "foliojs/pdfkit", "mozilla/pdf.js",
    "puppeteer/puppeteer", "wkhtmltopdf/wkhtmltopdf", "jgraph/drawio", "nomic-ai/gpt4all",
    # OCR-powered consumer apps (translation/screenshot/image editors) + DMS apps + benchmarks
    "sharex/sharex", "tisfeng/easydict", "t8rin/imagetoolbox", "pot-app/pot-desktop",
    "hillya51/lunatranslator", "stranslate/stranslate", "zyddnys/manga-image-translator",
    "xushengfeng/esearch", "thejoefin/text-grab", "paperless-ngx/paperless-ngx",
    "yusufkaraaslan/skill_seekers", "dataelement/bisheng", "run-llama/parsebench", "icereed/paperless-gpt",
}
_DENY -= _ALLOW
_ANTI = re.compile(
    r"\b(awesome|curated list|tutorials?|course|roadmap|cheat ?sheet|paper[- ]?(list|survey)|reading list"
    r"|for[- ]beginners|from[- ]scratch|book\b|inference (engine|server)|vector (database|db|store)"
    r"|\brag\b framework|retrieval[- ]augmented|chat ?(ui|bot clone)|chatgpt clone|web ?ui for"
    r"|stable diffusion|text[- ]to[- ]image|image generation|diffusion model|\btts\b|speech[- ]to[- ]text"
    r"|fine[- ]?tun|object detection model|\byolo\b|segment anything|model context protocol|\bmcp\b"
    r"|html to pdf|pdf generation|generate pdf|pdf viewer|pdf editor|pdf merge|markdown editor"
    r"|translat(e|or|ion)|screenshot|screen (capture|record)|dictionary|\bmanga\b|visual novel"
    r"|image (editor|toolbox)|document management|\bbenchmark\b|划词|截屏|翻译|词典"
    r"|note[- ]?taking|\bnotion\b|\bobsidian\b|password|encrypt pdf|e[- ]?sign)\b", re.I)


def gh(url: str, *, retries: int = 4):
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429):
                reset = e.headers.get("X-RateLimit-Reset")
                wait = 5 * (attempt + 1)
                if reset:
                    try:
                        wait = max(wait, min(60, int(reset) - int(time.time()) + 2))
                    except ValueError:
                        pass
                print(f"  rate-limited — sleeping {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if 500 <= e.code < 600:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(3 * (attempt + 1))
    if last:
        raise last
    raise RuntimeError(f"gh failed: {url}")


def search(q: str, per_page: int = 40) -> list[dict]:
    url = (f"{API}/search/repositories?q={urllib.parse.quote(q)}"
           f"&sort=stars&order=desc&per_page={per_page}")
    try:
        return gh(url).get("items", [])
    except Exception as e:
        print(f"  query failed [{q}]: {e}", file=sys.stderr)
        return []


def is_doc(r: dict) -> bool:
    full = (r.get("full_name") or "").lower()
    if full in _ALLOW:
        return True
    if full in _DENY:
        return False
    name = r.get("name") or ""
    desc = r.get("description") or ""
    if _ANTI.search(f"{name} {desc}"):
        return False
    topics = {t.lower() for t in (r.get("topics") or [])}
    if topics & _DOC_TOPICS:
        return True
    return bool(_DOC_PHRASES.search(f"{name} {desc}"))


def categorize(r: dict) -> str:
    nd = f"{(r.get('name') or '').lower()} {(r.get('description') or '').lower()}"
    if re.search(r"awesome|curated|\blist of\b|directory|catalog", nd):
        return "Collections"
    if re.search(r"table (extraction|recognition|detection)|extract tables|\bcamelot\b|table[- ]transformer|img2table", nd):
        return "Table Extraction"
    if re.search(r"layout (analysis|detection|parser)|document layout|reading order|page (segmentation|structure)|layoutparser", nd):
        return "Layout & Structure"
    if re.search(r"vision[- ]language|\bvlm\b|donut|nougat|olmocr|got[- ]ocr|multimodal.*document|image[- ]to[- ]text model"
                 r"|document (understanding|intelligence|question answering)|docvqa", nd):
        return "VLM & Understanding"
    if re.search(r"\bocr\b|optical character|handwriting|text recognition|scene text|tesseract|paddleocr|easyocr|trocr", nd):
        return "OCR Engines"
    if re.search(r"\bpdf\b|extract text|pdf to (markdown|text|json|html)|pdfplumber|pymupdf|parse pdf", nd):
        return "PDF Extraction"
    if re.search(r"document (parsing|processing|extraction|ai)|unstructured|docling|parse documents?|markitdown|grobid|toolkit|pipeline", nd):
        return "Document Parsing"
    return "Document Parsing"


def days_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 86400.0
    except ValueError:
        return None


def momentum(r: dict, max_stars: int) -> int:
    stars = r.get("stargazers_count", 0) or 0
    star_norm = math.log10(stars + 1) / math.log10(max(max_stars, 10) + 1)
    pushed = days_since(r.get("pushed_at"))
    recency = 0.2 if pushed is None else max(0.0, 1.0 - max(0.0, pushed) / 180.0)
    created = days_since(r.get("created_at"))
    young = (1.0 - created / 120.0) if (created is not None and created < 120 and stars >= 20) else 0.0
    return max(1, min(100, round((0.55 * star_norm + 0.32 * recency + 0.13 * young) * 100)))


def slugify(full_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", full_name.lower()).strip("-")


def build_items() -> list[dict]:
    seen: dict[str, dict] = {}
    for q in QUERIES:
        for r in search(q):
            full = r.get("full_name")
            if full and full not in seen and is_doc(r):
                seen[full] = r
        time.sleep(0.7)
    raw = list(seen.values())
    max_stars = max((r.get("stargazers_count", 0) or 0) for r in raw) if raw else 10
    items = []
    for r in raw:
        owner = r.get("owner") or {}
        items.append({
            "name": r.get("name", ""), "full_name": r.get("full_name", ""),
            "slug": slugify(r.get("full_name", "")), "url": r.get("html_url", ""),
            "owner": owner.get("login", ""), "owner_avatar": owner.get("avatar_url", ""),
            "stars": r.get("stargazers_count", 0) or 0, "forks": r.get("forks_count", 0) or 0,
            "open_issues": r.get("open_issues_count", 0) or 0, "language": r.get("language") or "",
            "license": ((r.get("license") or {}) or {}).get("spdx_id") or "",
            "pushed_at": r.get("pushed_at"), "created_at": r.get("created_at"),
            "description": (r.get("description") or "").strip(), "topics": r.get("topics") or [],
            "category": categorize(r), "momentum": momentum(r, max_stars),
        })
    items.sort(key=lambda x: (x["momentum"], x["stars"]), reverse=True)
    for i, it in enumerate(items, 1):
        it["rank"] = i
    return items


def write_json(items: list[dict]) -> dict:
    cats: dict[str, int] = {}
    for it in items:
        cats[it["category"]] = cats.get(it["category"], 0) + 1
    data = {"generated_at": datetime.now(timezone.utc).isoformat(), "count": len(items),
            "categories": [{"name": k, "count": v} for k, v in sorted(cats.items(), key=lambda x: -x[1])],
            "items": items}
    with open(os.path.join(HERE, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return data


def write_seo(data: dict) -> None:
    items = data["items"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [f"  <url><loc>{SITE_URL}/</loc><lastmod>{now}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>"]
    for it in items:
        urls.append(f"  <url><loc>{SITE_URL}/p/{it['slug']}/</loc><lastmod>{now}</lastmod>"
                    f"<changefreq>weekly</changefreq><priority>0.6</priority></url>")
    open(os.path.join(HERE, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n</urlset>\n")
    open(os.path.join(HERE, "robots.txt"), "w", encoding="utf-8").write(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")

    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    rss_items = [
        f"    <item><title>{esc(it['full_name'])} — momentum {it['momentum']}</title>"
        f"<link>{SITE_URL}/p/{it['slug']}/</link><guid isPermaLink=\"false\">{esc(it['full_name'])}</guid>"
        f"<description>{esc(it['description'][:300])}</description></item>" for it in items[:30]]
    open(os.path.join(HERE, "rss.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n  <channel>\n'
        f"    <title>{SITE_NAME}</title>\n    <link>{SITE_URL}</link>\n"
        "    <description>The living index of document-AI tooling — OCR, PDF extraction, document parsing, layout, tables and VLM understanding.</description>\n"
        + "\n".join(rss_items) + "\n  </channel>\n</rss>\n")

    lines = [f"# {SITE_NAME}", "",
             "> The living index of document-AI tooling — OCR, PDF extraction, document parsing, layout",
             "> & structure, table extraction and vision-language understanding — ranked daily by GitHub momentum.", "",
             f"Updated: {data['generated_at']}", f"Tools indexed: {data['count']}", "",
             "## Top document-AI tools by momentum", ""]
    for it in items[:40]:
        lines.append(f"- [{it['full_name']}]({it['url']}) — momentum {it['momentum']}, "
                     f"⭐{it['stars']} — {it['category']} — {it['description'][:100]}")
    open(os.path.join(HERE, "llms.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main() -> int:
    if not token():
        print("WARNING: no GITHUB_TOKEN — low rate limit, partial results", file=sys.stderr)
    items = build_items()
    if not items:
        print("ERROR: no document tools found — refusing to write empty data.json", file=sys.stderr)
        return 1
    data = write_json(items)
    write_seo(data)
    print(f"wrote data.json: {len(items)} document-AI tools across {len(data['categories'])} categories")
    print("  top 5:", ", ".join(f"{it['full_name']}({it['momentum']})" for it in items[:5]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
