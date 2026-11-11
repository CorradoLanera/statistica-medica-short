#!/usr/bin/env python3
"""Post-render di Quarto: niente a capo fra una formula in linea e la sua punteggiatura.

Chrome tratta il <math> in linea come un blocco atomico e puo' andare a capo
subito prima o subito dopo, anche senza spazio: «(» resta in fondo alla riga
e la formula comincia la riga dopo, oppure «)» o «.» finiscono a capo da soli.
Lo script avvolge la parentesi aperta, la formula e la punteggiatura che la
segue in uno span con white-space: nowrap. La formula stessa non cambia.

Gira dopo ogni render (project: post-render in _quarto.yml) sui file HTML
delle slide; si puo' anche lanciare a mano: python dev/fix_math_wrap.py
"""

import os
import pathlib
import re

MARK = 'class="mnw"'
INLINE = re.compile(
    r'([(\[«]*)(<math display="inline"[^>]*>.*?</math>)([)\]».,;:!?]*)', re.S)


def wrap(m):
    if not m.group(1) and not m.group(3):
        return m.group(0)
    return '<span %s style="white-space:nowrap">%s</span>' % (MARK, m.group(0))


def fix(path):
    text = path.read_text(encoding="utf-8")
    if MARK in text:  # gia' sistemato
        return 0
    new, n = INLINE.subn(wrap, text)
    if new != text:
        path.write_text(new, encoding="utf-8", newline="\n")
    return new.count(MARK)


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
                print(f"fix_math_wrap: {f.name}: {n} formule")


if __name__ == "__main__":
    main()
