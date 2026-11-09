#!/usr/bin/env python3
"""Converte un deck xaringan (.Rmd) in un deck Quarto revealjs (.qmd).

Uso:
    python dev/xaringan2quarto.py slides/00-intro_and_info.Rmd slides/00-intro_and_info.qmd

La conversione e' meccanica e conserva il contenuto. Su stderr scrive
l'elenco dei punti da controllare a mano (classi sconosciute, blocchi
rimossi, proprieta' di slide non tradotte).

Che cosa traduce:

- separatori `---` e prima intestazione della slide -> `## Titolo {attributi}`;
- `class:` della slide (inverse, middle, center, right) -> classi e sfondo;
- `.classe[...]` di remark -> span `[...]{.classe}` o div `::: {.classe}`;
- `.panelset[.panel[.panel-name[Nome] ...]]` -> `::: {.panel-tabset}` con `### Nome`;
- `.pull-left/.pull-right`, `.left-column/.right-column` e simili -> colonne;
- blocchi `<small>` ... `</small>` su righe proprie -> `::: {.small}`;
- chunk di configurazione di xaringan (xaringanExtra, xaringanthemer, css) -> rimossi.
"""

import re
import sys

COLUMNS = {
    "pull-left": ("L", "48%"),
    "pull-right": ("R", "48%"),
    "left-column": ("L", "22%"),
    "right-column": ("R", "75%"),
    "rigth-column": ("R", "75%"),
    "left-code": ("L", "40%"),
    "right-code": ("R", "57%"),
    "left-plot": ("L", "40%"),
    "right-plot": ("R", "57%"),
}
ALIGN = {
    "center": "text-center",
    "left": "text-left",
    "right": "text-right",
    "rigth": "text-right",
    "tr": "text-right",
}
SLIDE_PROPS = re.compile(
    r"^(class|name|background-image|background-size|background-position|count|layout|exclude|seal):\s*(.*?)\s*$"
)
INVERSE_BG = "#03A696"
DROP_LIBS = {"xaringanExtra", "xaringanthemer", "metathis"}

report = []


def note(msg):
    report.append(msg)


# --------------------------------------------------------------------------
# Mascheramento: codice, formule e commenti non devono essere toccati.
# --------------------------------------------------------------------------

class Masker:
    def __init__(self):
        self.store = []

    def _put(self, s):
        self.store.append(s)
        return "\x00%d\x00" % (len(self.store) - 1)

    def mask(self, text):
        pats = [
            re.compile(r"^[ \t]*```.*?^[ \t]*```[ \t]*$", re.S | re.M),  # chunk
            re.compile(r"<!--.*?-->", re.S),                          # commenti
            re.compile(r"\$\$.*?\$\$", re.S),                         # display
            re.compile(r"`[^`\n]+`"),                                 # codice inline
            re.compile(r"(?<![\\$])\$(?![\s$])(?:\\.|[^$\n\\])+?(?<!\s)\$(?!\d)"),  # inline math
        ]
        for p in pats:
            text = p.sub(lambda m: self._put(m.group(0)), text)
        return text

    def unmask(self, text):
        # piu' passate: un token puo' contenerne altri
        for _ in range(5):
            new = re.sub(r"\x00(\d+)\x00", lambda m: self.store[int(m.group(1))], text)
            if new == text:
                break
            text = new
        return text


# --------------------------------------------------------------------------
# Classi di remark: .classe[ ... ]
# --------------------------------------------------------------------------

OPENER = re.compile(r"(?<![A-Za-z0-9\\.])\.([A-Za-z][\w-]*(?:\.[A-Za-z][\w-]*)*)\[")


def find_close(text, start):
    """Indice della ] che chiude la [ aperta subito prima di start."""
    depth = 1
    i = start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def bump_headings(text):
    return re.sub(r"^(#{3,5})(?= )", lambda m: m.group(1) + "#", text, flags=re.M)


def whole_line(text, p, end):
    line_start = text.rfind("\n", 0, p) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end < 0 else line_end
    return text[line_start:p].strip() == "" and text[end + 1:line_end].strip() == ""


def convert_classes(text):
    out = []
    pos = 0
    while True:
        m = OPENER.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        p, inner_start = m.start(), m.end()
        end = find_close(text, inner_start)
        if end < 0:
            note("parentesi non chiusa dopo '%s'" % text[p:p + 40].replace("\n", " "))
            out.append(text[pos:inner_start])
            pos = inner_start
            continue
        classes = m.group(1).split(".")
        name = classes[0]
        out.append(text[pos:p])

        if name in COLUMNS and len(classes) == 1:
            cols = []
            cur_p, cur_inner, cur_end, cur_name = p, inner_start, end, name
            while True:
                cols.append((cur_name, text[cur_inner:cur_end]))
                look = cur_end + 1
                while look < len(text) and text[look] in " \t\n":
                    look += 1
                m2 = OPENER.match(text, look)
                if m2 and m2.group(1) in COLUMNS:
                    e2 = find_close(text, m2.end())
                    if e2 < 0:
                        break
                    cur_inner, cur_end, cur_name = m2.end(), e2, m2.group(1)
                    continue
                break
            parts = []
            only_right = all(COLUMNS[c][0] == "R" for c, _ in cols)
            for c, body in cols:
                width = COLUMNS[c][1]
                extra = ' style="margin-left: auto;"' if only_right else ""
                parts.append('::: {.column width="%s"%s}\n%s\n:::' % (width, extra, convert_classes(body).strip("\n")))
            out.append("\n:::: {.columns}\n" + "\n\n".join(parts) + "\n::::\n")
            pos = cur_end + 1
            continue

        body = text[inner_start:end]
        if name == "panelset":
            out.append("\n::: {.panel-tabset}\n" + convert_classes(body).strip("\n") + "\n:::\n")
        elif name == "panel":
            mn = re.match(r"\s*\.panel-name\[", body)
            if mn:
                e3 = find_close(body, mn.end())
                title = body[mn.end():e3].strip()
                rest = body[e3 + 1:]
            else:
                title, rest = "Pannello", body
                note("pannello senza .panel-name")
            out.append("\n### %s\n\n%s\n" % (convert_classes(title), bump_headings(convert_classes(rest)).strip("\n")))
        elif name == "footnote":
            out.append("\n::: aside\n" + convert_classes(body).strip("\n") + "\n:::\n")
        elif "bg-washed-green" in classes:
            out.append("\n::: {.quote-box}\n" + convert_classes(body).strip("\n") + "\n:::\n")
        else:
            css = [ALIGN.get(c, c) for c in classes]
            known = {"orange", "red", "purple", "green", "white", "black", "pastel_orange", "blu_gray"} | set(ALIGN.values())
            for c in css:
                if c not in known:
                    note("classe '%s' lasciata com'e': va definita nel tema o tolta" % c)
            attr = "{" + " ".join("." + c for c in css) + "}"
            inner = convert_classes(body)
            is_block = "\n" in body.strip("\n") or (name in ALIGN and whole_line(text, p, end))
            if is_block:
                out.append("\n::: %s\n%s\n:::\n" % (attr, inner.strip("\n")))
            else:
                out.append("[%s]%s" % (inner, attr))
        pos = end + 1
    return "".join(out)


# --------------------------------------------------------------------------
# Slide
# --------------------------------------------------------------------------

HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
FENCE = re.compile(r"^:{3,}")


LIST_ITEM = re.compile(r"^([ \t]*(?:>[ \t]*)*)([-+*]|\d+[.)])[ \t]+\S")


def blank_before_lists(text):
    """Pandoc, a differenza di remark, vuole una riga vuota prima di un elenco."""
    out = []
    for ln in text.split("\n"):
        m = LIST_ITEM.match(ln)
        if m and out:
            prev = out[-1]
            core = re.sub(r"^[ \t]*(?:>[ \t]*)*", "", prev)
            if (core.strip() != "" and not LIST_ITEM.match(prev)
                    and not prev.startswith((" ", "\t"))
                    and not FENCE.match(prev) and not HEADING.match(prev)):
                out.append(m.group(1).rstrip() if ">" in m.group(1) else "")
        out.append(ln)
    return "\n".join(out)


def space_fences(text):
    """Pandoc vuole una riga vuota prima e dopo ogni recinto ::: di un div."""
    out = []
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if FENCE.match(ln) and out and out[-1].strip() != "":
            out.append("")
        if out and FENCE.match(out[-1] if out[-1] else "") and ln.strip() != "" and not FENCE.match(ln):
            out.append("")
        out.append(ln)
    return "\n".join(out)


def slide_attrs(props):
    classes, kv = [], []
    for k, v in props:
        if k == "class":
            for c in [x.strip() for x in v.split(",") if x.strip()]:
                if c == "inverse":
                    classes.append("inverse")
                    kv.append('background-color="%s"' % INVERSE_BG)
                elif c == "middle":
                    classes.append("center")
                elif c == "center":
                    classes.append("text-center")
                elif c == "right":
                    classes.append("text-right")
                elif c in ("hide-count", "hide_logo", "hide-logo", "bg_title", "left", "top"):
                    pass
                else:
                    note("classe di slide '%s' non tradotta" % c)
        elif k == "name":
            classes.insert(0, "#" + v)
        elif k == "background-image":
            url = re.sub(r"^url\((.*)\)$", r"\1", v)
            kv.append('background-image="%s"' % url)
        elif k == "background-size":
            kv.append('background-size="%s"' % v)
        elif k == "background-position":
            kv.append('background-position="%s"' % v)
        else:
            note("proprieta' di slide '%s: %s' ignorata" % (k, v))
    parts = []
    for c in classes:
        parts.append(c if c.startswith("#") else "." + c)
    parts.extend(kv)
    return ("{" + " ".join(parts) + "}") if parts else ""


def convert_slide(raw):
    lines = raw.split("\n")
    while lines and lines[0].strip() == "":
        lines.pop(0)
    props = []
    while lines and SLIDE_PROPS.match(lines[0]):
        mm = SLIDE_PROPS.match(lines[0])
        props.append((mm.group(1), mm.group(2)))
        lines.pop(0)
    attrs = slide_attrs(props)

    title = None
    first = None
    for i, ln in enumerate(lines):
        if HEADING.match(ln):
            first = i
            break
    if first is not None:
        before = [l for l in lines[:first] if l.strip() not in ("", "<br>", "<br/>", "<br />")]
        if not before:
            title = HEADING.match(lines[first]).group(2)
            lines = lines[first + 1:]
    body = []
    for ln in lines:
        mh = HEADING.match(ln)
        if mh:
            level = len(mh.group(1))
            text = mh.group(2)
            if title is None and level == 1:
                body.append("### %s {.big}" % text)
            else:
                body.append("%s %s" % ("#" * max(3, level + 1), text))
        else:
            body.append(ln)
    text = "\n".join(body)
    text = convert_classes(text)
    text = re.sub(r"^[ \t]*<small>[ \t]*$", "::: {.small}", text, flags=re.M)
    text = re.sub(r"^[ \t]*</small>[ \t]*$", ":::", text, flags=re.M)
    # un <small> senza </small> in xaringan finiva con la slide: qui va chiuso
    opens = len(re.findall(r"^:{3,}[ \t]*(\{|\w)", text, flags=re.M))
    closes = len(re.findall(r"^:{3,}[ \t]*$", text, flags=re.M))
    if opens > closes:
        note("%d div chiusi d'ufficio a fine slide" % (opens - closes))
        text = text.rstrip("\n") + "\n" + "\n:::" * (opens - closes) + "\n"
    # in xaringan "@nome" e' testo; per Pandoc sarebbe una citazione
    text = re.sub(r"(?<![A-Za-z0-9._%+\-\\])@", r"\\@", text)
    # grassetto con __x__: Pandoc non lo riconosce attaccato ad altro grassetto
    text = re.sub(r"(?<![\w_])__(?=\S)(.+?)(?<=\S)__(?![\w_])", r"**\1**", text)
    text = text.replace("****", "")
    text = blank_before_lists(text)
    text = space_fences(text)
    text = re.sub(r"\n{4,}", "\n\n\n", text).strip("\n")

    if title is not None:
        head = "## " + convert_classes(title) + ((" " + attrs) if attrs else "")
    elif attrs:
        head = "## " + attrs
    else:
        head = "---"
    return head + "\n\n" + text + "\n"


# --------------------------------------------------------------------------
# Chunk di configurazione
# --------------------------------------------------------------------------

def clean_chunk(chunk):
    header = chunk.split("\n", 1)[0]
    if re.match(r"^[ \t]*```\{css", header):
        note("chunk css rimosso: le regole vanno nel tema SCSS")
        return ""
    body = chunk
    if re.search(r"\buse_(tachyons|share_again|panelset|clipboard|editable|freezeframe|extra_styles|progress_bar|logo)\(|style_(duo_accent|share_again|xaringan|mono_accent)\(", body):
        note("chunk di xaringan rimosso: %s" % header.strip())
        return ""
    new = []
    for ln in body.split("\n"):
        ml = re.match(r"^\s*library\((\w+)\)\s*$", ln)
        if ml and ml.group(1) in DROP_LIBS:
            continue
        if "htmltools.dir.version" in ln:
            continue
        new.append(ln)
    return "\n".join(new)


def front_matter(yaml_text, subtitle):
    def field(name):
        mm = re.search(r'^%s:\s*"?(.*?)"?\s*$' % name, yaml_text, re.M)
        return mm.group(1) if mm else ""
    title = field("title") or "STATISTICA MEDICA"
    sub = subtitle or field("subtitle")
    return "\n".join([
        "---",
        'title: "%s"' % title,
        'subtitle: "%s"' % sub.replace('"', '\\"'),
        'author: "Corrado Lanera"',
        'institute: "[Unità di Biostatistica, Epidemiologia e Salute Pubblica](https://www.unipd-ubep.it/), Università di Padova"',
        "date: last-modified",
        'date-format: "D MMMM YYYY"',
        "lang: it",
        "format:",
        "  revealjs:",
        "    theme: [default, statmed.scss]",
        "    template-partials: [title-slide.html]",
        "    width: 960",
        "    height: 720",
        "    margin: 0.06",
        "    slide-number: true",
        "    progress: true",
        "    logo: img/unipd_logo.png",
        '    footer: "Statistica Medica · [bit.ly/cl-statmed](https://bit.ly/cl-statmed)"',
        "    embed-resources: true",
        "    code-copy: true",
        "    auto-stretch: false",
        "    menu:",
        "      side: left",
        "execute:",
        "  cache: false",
        "---",
        "",
    ])


def main(src, dst):
    text = open(src, encoding="utf-8").read().replace("\r\n", "\n")
    mfm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    yaml_text = mfm.group(1) if mfm else ""
    body = text[mfm.end():] if mfm else text

    # chunk di configurazione
    body = re.sub(r"^[ \t]*```\{.*?^[ \t]*```[ \t]*$",
                  lambda m: clean_chunk(m.group(0)), body, flags=re.S | re.M)

    masker = Masker()
    masked = masker.mask(body)
    raw_slides = re.split(r"^---[ \t]*$", masked, flags=re.M)

    # la prima slide (titolo fatto a mano) diventa la slide del titolo di Quarto
    first = raw_slides[0]
    subtitle = ""
    ms = re.search(r"^--\s*(.+?)\s*--\s*$", masker.unmask(first), re.M)
    if ms:
        subtitle = ms.group(1)
    setup = [masker.unmask(t) for t in re.findall(r"\x00\d+\x00", first)
             if masker.unmask(t).lstrip().startswith("```{r")]
    setup = [s for s in setup if s.strip()]
    note("slide del titolo sostituita da quella di Quarto (sottotitolo: '%s')" % subtitle)

    out = [front_matter(yaml_text, subtitle)]
    out.extend(s + "\n" for s in setup)
    for raw in raw_slides[1:]:
        if raw.strip() == "":
            continue
        out.append(convert_slide(raw))
    result = masker.unmask("\n".join(out))
    result = re.sub(r"\n{4,}", "\n\n\n", result)
    open(dst, "w", encoding="utf-8", newline="\n").write(result)
    for r in report:
        print("- " + r, file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
