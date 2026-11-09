"""Controlli statici sul sito in docs/: risorse esterne nelle slide (offline) e link interni rotti.

Uso: python dev/check_site_static.py . links.json, poi python dev/check_links.py links.json
"""
import re, sys, json, os
from pathlib import Path
from urllib.parse import urlparse, unquote
root = Path(sys.argv[1]); out = Path(sys.argv[2])
docs = root / "docs"
skip_dirs = {"site_libs", "xaringan", "_freeze"}
pages = [p for p in docs.rglob("*.html") if not (set(p.relative_to(docs).parts) & skip_dirs)]
ext_links = {}
broken = []
offline = []
attr = re.compile(r'<(a|img|script|link|iframe|source|video|audio)\b[^>]*?\s(href|src)\s*=\s*"([^"]*)"', re.I | re.S)
for p in pages:
    h = p.read_text(encoding="utf-8", errors="replace")
    rel = p.relative_to(docs).as_posix()
    is_slide = rel.startswith("slides/") and rel != "slides/index.html"
    for tag, a, url in attr.findall(h):
        if "${" in url or "'+" in url:  # stringhe dentro il JavaScript, non link
            continue
        tag = tag.lower()
        if url.startswith("data:") or url.startswith("#") or url.startswith("mailto:") or url.startswith("javascript:") or url == "":
            continue
        u = urlparse(url)
        if u.scheme in ("http", "https"):
            if tag == "a":
                ext_links.setdefault(url, set()).add(rel)
            elif is_slide:
                offline.append((rel, tag, url))
            continue
        if u.scheme:
            continue
        target = (p.parent / unquote(u.path)).resolve() if u.path else p
        if u.path.startswith("/"):
            target = (docs / unquote(u.path).lstrip("/")).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            broken.append((rel, tag, url))
    if is_slide:
        for m in re.findall(r'url\(\s*["\']?(https?://[^)"\']+)', h):
            offline.append((rel, "css-url", m))
        for m in re.findall(r'@import\s+["\']?(https?://[^"\';]+)', h):
            offline.append((rel, "css-import", m))
print("pagine:", len(pages))
print("risorse esterne nelle slide (offline):", len(offline))
for r in sorted(set(offline))[:40]: print("  ", r)
print("link interni rotti:", len(broken))
for r in sorted(set(broken))[:60]: print("  ", r)
json.dump({k: sorted(v) for k, v in ext_links.items()}, open(out, "w", encoding="utf-8"), indent=0, ensure_ascii=False)
print("link esterni distinti:", len(ext_links))
