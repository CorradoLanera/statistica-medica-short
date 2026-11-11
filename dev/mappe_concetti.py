"""Genera le slide con le mappe dei concetti (una per sezione, una per deck)
e la mappa del corso, da dev/concetti.json.

Uso, dalla radice del progetto, dopo un render delle slide:

    python dev/mappe_concetti.py
    quarto render

I link dell'indice puntano agli id delle slide, che lo script legge dagli HTML
in docs/slides/: se si rinomina una slide, si rilancia lo script dopo il primo
render e si renderizza di nuovo. Scrive slides/_mappe/<deck>-<sezione>.qmd,
slides/_mappe/<deck>-deck.qmd e slides/_mappe/corso.qmd; i deck li includono
con {{< include _mappe/... >}}.
"""
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "slides" / "_mappe"
DECKS = {
    "01": ("01-r_rstudio", "R e RStudio"),
    "02": ("02-descrittive", "Statistiche descrittive"),
    "03": ("03-probabilita", "Probabilità"),
    "04": ("04-distribuzioni", "Distribuzioni"),
    "05": ("05-ic_p", "Stime, intervalli e test"),
}
SECTION_TITLE = {
    "01.1": "R e RStudio in breve",
    "01.2": "R",
    "02.1": "Oggetti in gioco",
    "02.2": "Localizzazione",
    "02.3": "Rappresentazione",
    "03.1": "Definizioni e notazioni",
    "03.2": "Operazioni di base",
    "03.3": "Condizionamento e test diagnostici",
    "03.4": "Teorema di Bayes",
    "04.1": "Modelli discreti",
    "04.2": "Binomiale",
    "04.3": "Poisson",
    "04.4": "Variabili continue",
    "04.5": "Normale",
    "05.1": "Inferenza",
    "05.2": "Stime puntuali",
    "05.3": "Precisione delle stime",
    "05.4": "Esempi e osservazioni",
    "05.5": "t di Student",
    "05.6": "Test d'ipotesi",
}
MIN_SECTION = 3  # sotto questa soglia i concetti stanno solo nella mappa del deck
# carattere di sistema per le etichette (lo stesso che impone statmed.scss):
# con il carattere web delle slide Mermaid le misura prima che sia caricato e
# poi le taglia
# htmlLabels false: con le etichette HTML Mermaid misura i riquadri con
# getBoundingClientRect, che sente la scala di reveal.js; al telefono le slide
# sono rimpicciolite e i riquadri uscivano stretti, con il testo tagliato.
# Le etichette SVG si misurano in coordinate proprie, a ogni scala.
INIT = (
    '%%{init: {"htmlLabels": false, "flowchart": {"padding": 12, "wrappingWidth": 320}, '
    '"themeVariables": {"fontFamily": "Arial, Helvetica, sans-serif"}}}%%\n'
)

STYLE = [
    "classDef cur fill:#e6f0fa,stroke:#035AA6,color:#000000",
    "classDef prev fill:#f4f4f4,stroke:#9a9a9a,color:#555555,stroke-dasharray:4 3",
    "classDef opt fill:#ffffff,stroke:#035AA6,color:#555555,stroke-dasharray:2 2",
]


def norm(t):
    return re.sub(r"\W+", "", t.lower())


def slide_ids(deck_file):
    """(titolo normalizzato, occorrenza) -> id, dall'HTML renderizzato."""
    h = (ROOT / "docs" / "slides" / f"{deck_file}.html").read_text(encoding="utf-8")
    ids, seen = {}, defaultdict(int)
    for m in re.finditer(r"<section\b([^>]*)>\s*(<h2[^>]*>(.*?)</h2>)?", h, re.S):
        sid = re.search(r'\bid="([^"]+)"', m.group(1))
        cls = re.search(r'\bclass="([^"]*)"', m.group(1))
        if not (m.group(2) and sid and cls and "level2" in cls.group(1).split()):
            continue
        text = re.sub(r"<math\b.*?</math>", "", m.group(3), flags=re.S)
        n = norm(html.unescape(re.sub(r"<[^>]+>", "", text)))
        ids[(n, seen[n])] = sid.group(1)
        seen[n] += 1
    return ids


def node(cid):
    return "n_" + re.sub(r"\W", "_", cid)


def q(label):
    return '"' + label.replace('"', "'") + '"'


def reduce(edges):
    """Riduzione transitiva: toglie u->v se v è raggiungibile da u per un'altra via."""
    out = defaultdict(set)
    for u, v in edges:
        out[u].add(v)

    def reach(a, b, skip):
        stack, seen = [a], set()
        while stack:
            x = stack.pop()
            for y in out[x]:
                if (x, y) == skip or y in seen:
                    continue
                if y == b:
                    return True
                seen.add(y)
                stack.append(y)
        return False

    return sorted((u, v) for u, v in set(edges) if not reach(u, v, (u, v)))


def direction(nodes, edges):
    """LR se il grafo è più profondo che largo, altrimenti TB."""
    pred = defaultdict(set)
    for u, v in edges:
        pred[v].add(u)
    level = {}

    def lev(n, path=()):
        if n not in level:
            up = [lev(p, path + (n,)) for p in pred[n] if p not in path]
            level[n] = 1 + max(up) if up else 0
        return level[n]

    for n in nodes:
        lev(n)
    depth = 1 + max(level.values(), default=0)
    width = max(sum(1 for n in nodes if level[n] == k) for k in range(depth))
    lr = min(900 / (depth * 190), 470 / (width * 48))
    tb = min(900 / (width * 190), 470 / (depth * 70))
    return "LR" if lr >= tb else "TB"


def mermaid(lines, init=INIT):
    return "```{mermaid}\n%%| echo: false\n" + init + "\n".join(lines) + "\n```\n"


def legend(extra=""):
    return (
        "\n::: {.mappa-legenda}\n\nOgni freccia va da un concetto a quelli che lo usano."
        f"{extra}\n\n:::\n"
    )


def main():
    data = json.loads((ROOT / "dev" / "concetti.json").read_text(encoding="utf-8"))
    C = {c["id"]: c for c in data["concepts"]}
    chunk = {ch["id"]: ch for ch in data["chunks"]}
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.qmd"):
        old.unlink()
    missing = []
    order = list(DECKS)
    deck_files = {}

    for d, (fname, dtitle) in DECKS.items():
        ids = slide_ids(fname)
        mine = [c for c in C.values() if c["deck"] == d]
        mine.sort(key=lambda c: (c["section"], c.get("slide_k") or 0))

        def link(c):
            key = (c["slide_norm"], c["slide_k"])
            if key not in ids:
                missing.append(f"{d} {c['id']}: slide «{c['slide']}» non trovata")
                return c["short"]
            return f"[{c['short']}](#{ids[key]})"  # reveal.js aggiunge da sé la barra di #/

        by_sec = defaultdict(list)
        for c in mine:
            by_sec[c["section"]].append(c)
        files = []
        for sec in sorted(by_sec):
            cs = by_sec[sec]
            if len(cs) < MIN_SECTION or sec not in SECTION_TITLE:
                continue
            S = {c["id"] for c in cs}
            ext_same, ext_other = set(), defaultdict(set)
            edges = []
            for c in cs:
                for r in c["requires"]:
                    if r not in C:
                        continue
                    if r in S:
                        edges.append((node(r), node(c["id"])))
                    elif C[r]["deck"] == d:
                        ext_same.add(r)
                        edges.append((node(r), node(c["id"])))
                    else:
                        ch = C[r]["chunk"]
                        ext_other[ch].add(r)
                        edges.append(("k_" + node(ch), node(c["id"])))
            edges = reduce(edges)
            nodes = [node(i) for i in S] + [node(i) for i in ext_same] + ["k_" + node(k) for k in ext_other]
            g = ["flowchart " + direction(nodes, edges)]
            for r in sorted(ext_same, key=lambda r: (C[r]["section"], r)):
                g.append(f"  {node(r)}[{q(C[r]['short'])}]:::prev")
            for k in sorted(ext_other):
                g.append(f"  k_{node(k)}[{q(chunk[k]['label'] + ' · ' + chunk[k]['deck'])}]:::prev")
            for c in cs:
                cls = "opt" if c["optional"] else "cur"
                g.append(f"  {node(c['id'])}[{q(c['short'])}]:::{cls}")
            g += [f"  {u} --> {v}" for u, v in edges]
            g += ["  " + s for s in STYLE]
            idx = "\n".join(
                f"- {link(c)}" + (" (facoltativo)" if c["optional"] else "") for c in cs
            )
            title = SECTION_TITLE[sec]
            txt = (
                f"## Mappa: {title} {{.mappa}}\n\n::: {{.panel-tabset}}\n\n### Mappa\n\n"
                + mermaid(g)
                + legend(" In grigio i concetti delle sezioni o dei deck precedenti (con il numero del deck).")
                + "\n### Indice\n\n::: {.mappa-indice}\n\n" + idx + "\n\n:::\n\n:::\n"
            )
            f = OUT / f"{d}-{sec.split('.')[1]}.qmd"
            f.write_text(txt, encoding="utf-8")
            files.append(f.name)

        # mappa del deck: blocchi del deck e blocchi precedenti richiesti
        dch = [ch for ch in data["chunks"] if ch["deck"] == d]
        edges, ext = [], set()
        for ch in dch:
            for cid in ch["concepts"]:
                for r in C[cid]["requires"]:
                    if r in C and C[r]["chunk"] != ch["id"]:
                        src = C[r]["chunk"]
                        if chunk[src]["deck"] != d:
                            if order.index(chunk[src]["deck"]) > order.index(d):
                                continue
                            ext.add(src)
                        edges.append(("k_" + node(src), "k_" + node(ch["id"])))
        edges = reduce(edges)
        nodes = ["k_" + node(ch["id"]) for ch in dch] + ["k_" + node(k) for k in ext]
        g = ["flowchart " + direction(nodes, edges)]
        for k in sorted(ext):
            g.append(f"  k_{node(k)}[{q(chunk[k]['label'] + ' · ' + chunk[k]['deck'])}]:::prev")
        for ch in dch:
            n = len(ch["concepts"])
            opt = all(C[i]["optional"] for i in ch["concepts"])
            g.append(f"  k_{node(ch['id'])}[{q(ch['label'] + ' (' + str(n) + ')')}]:::{'opt' if opt else 'cur'}")
        g += [f"  {u} --> {v}" for u, v in edges]
        g += ["  " + s for s in STYLE]
        blocks = "\n".join(
            f"- **{ch['label']}**: " + ", ".join(link(C[i]) for i in ch["concepts"]) for ch in dch
        )
        txt = (
            "## Mappa: tutte le sezioni {.mappa}\n\n::: {.panel-tabset}\n\n### Mappa\n\n"
            + mermaid(g)
            + legend(" Ogni riquadro è un blocco di concetti che si usano insieme; fra parentesi quanti sono.")
            + "\n### Blocchi\n\n::: {.mappa-indice .mappa-blocchi}\n\n" + blocks + "\n\n:::\n\n:::\n"
        )
        f = OUT / f"{d}-deck.qmd"
        f.write_text(txt, encoding="utf-8")
        files.append(f.name)
        deck_files[d] = files

    # mappa del corso: tutti i blocchi, raggruppati per deck
    edges = []
    for ch in data["chunks"]:
        for cid in ch["concepts"]:
            for r in C[cid]["requires"]:
                if r in C and C[r]["chunk"] != ch["id"]:
                    edges.append(("k_" + node(C[r]["chunk"]), "k_" + node(ch["id"])))
    edges = reduce(edges)
    g = ["flowchart TB"]
    for d, (fname, dtitle) in DECKS.items():
        g.append(f'  subgraph d{d} ["{d} · {dtitle}"]')
        g.append("    direction LR")
        for ch in data["chunks"]:
            if ch["deck"] == d:
                opt = d == "01" or all(C[i]["optional"] for i in ch["concepts"])
                g.append(f"    k_{node(ch['id'])}[{q(ch['label'])}]:::{'opt' if opt else 'cur'}")
        g.append("  end")
    g += [f"  {u} --> {v}" for u, v in edges]
    g += ["  " + s for s in STYLE]
    # la mappa del corso sta in una pagina, non in una slide: niente scala di
    # reveal.js, e con le etichette SVG i sottografi si sovrappongono
    init = INIT.replace('"htmlLabels": false, ', "")
    (OUT / "corso.qmd").write_text(mermaid(g, init), encoding="utf-8")

    for d, files in deck_files.items():
        print(d, " ".join(files))
    if missing:
        print("\n".join(missing))
        sys.exit(1)


main()
