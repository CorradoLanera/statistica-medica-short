#!/usr/bin/env python3
"""Post-render di Quarto: sistema gli accenti (barre, cappelli) nel MathML delle slide.

Pandoc scrive \\bar{A} come <mover><mi>A</mi><mo accent="true">¯</mo></mover>.
Chrome, con l'attributo accent sull'<mo>, disegna la barra una seconda volta
piu' in alto, sopra la riga precedente. Con accent="true" sull'<mover> (e
l'<mo> senza attributo) la barra resta una sola, sopra la lettera.

Gira dopo ogni render (project: post-render in _quarto.yml) sui file HTML
delle slide; si puo' anche lanciare a mano: python dev/fix_mathml_accents.py
"""

import os
import pathlib
import re

ACCENT = re.compile(r'<mover>((?:(?!</?mover\b).)*?)<mo accent="true">([^<]*)</mo></mover>', re.S)


def fix(path):
    text = path.read_text(encoding="utf-8")
    # e la barra U+203E (overline), non U+00AF (macron), che Chrome appoggia
    # sulla lettera fino a toccarla
    new, n = ACCENT.subn(lambda m: '<mover accent="true">%s<mo>%s</mo></mover>'
                         % (m.group(1), m.group(2).replace("¯", "‾")), text)
    if n:
        path.write_text(new, encoding="utf-8", newline="\n")
    return n


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    listed = os.environ.get("QUARTO_PROJECT_OUTPUT_FILES", "")
    files = [pathlib.Path(f) for f in listed.splitlines() if f.strip()]
    if not files:
        files = list((root / "docs" / "slides").glob("*.html"))
    for f in files:
        f = f if f.is_absolute() else root / f
        if f.suffix == ".html" and "slides" in f.parts and f.exists():
            n = fix(f)
            if n:
                print("accenti MathML sistemati: %d in %s" % (n, f.name))


if __name__ == "__main__":
    main()
