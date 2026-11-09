"""Stato HTTP dei link esterni raccolti da check_site_static.py; stampa solo quelli non 2xx.

I DOI di OUP e BMJ rispondono 403 ai client automatici: non sono rotti.
"""
import json, sys, ssl
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
links = json.load(open(sys.argv[1], encoding="utf-8"))
ctx = ssl.create_default_context()
def check(url):
    for method in ("HEAD", "GET"):
        try:
            r = urlopen(Request(url, method=method, headers={"User-Agent": "Mozilla/5.0 (link-check)"}), timeout=20, context=ctx)
            return url, r.status, r.geturl()
        except HTTPError as e:
            if method == "HEAD" and e.code in (403, 404, 405, 400, 429, 500, 501, 503):
                continue
            return url, e.code, ""
        except Exception as e:
            if method == "HEAD":
                continue
            return url, type(e).__name__ + ": " + str(e)[:80], ""
with ThreadPoolExecutor(16) as ex:
    res = list(ex.map(check, links))
bad = [r for r in res if not (isinstance(r[1], int) and 200 <= r[1] < 300)]
print("controllati:", len(res), "non ok:", len(bad))
for url, st, fin in sorted(bad, key=lambda r: str(r[1])):
    print(st, url, "<-", ", ".join(links[url])[:90])
moved = [(u, f) for u, s, f in res if isinstance(s, int) and 200 <= s < 300 and f and f.rstrip("/") != u.rstrip("/") and "bit.ly" not in u]
print("redirect verso altro host:", len([1 for u, f in moved if u.split('/')[2] != f.split('/')[2]]))
for u, f in moved:
    if u.split('/')[2] != f.split('/')[2]: print("  ", u, "->", f[:100])
