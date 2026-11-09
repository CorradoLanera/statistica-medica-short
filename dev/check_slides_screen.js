// Uso: aprire docs/slides/0N-*.html in Chrome (finestra 1024x768) e lanciare questa
// funzione con evaluate_script di chrome-devtools MCP (sourcePath). Restituisce
// {slides, issues}: issues vuoto se nessuna slide o scheda esce dal fondo o dal bordo.
async () => {
  // Controllo a schermo di un deck revealjs: per ogni slide (e ogni scheda dei
  // riquadri a schede) contenuto oltre il fondo o il bordo destro, sintassi
  // rimasta come testo, immagini rotte, errori MathML, codice che scorre.
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const H = Reveal.getConfig().height, W = Reveal.getConfig().width;
  const LIMIT = H - 35; // sopra il piè di pagina
  const out = [];
  const raw = [
    [/\*\*[^*\n]+\*\*/, "**"], [/:::/, ":::"], [/\{\.[a-z]/, "{."], [/\]\{/, "]{"],
    [/\]\((https?:|\.|\/|#)/, "](link)"], [/\$[^$\n]{1,60}\$/, "$tex$"],
    [/\\(frac|bar|left|right|sqrt|sum|mu|sigma|alpha|text|mathrm|overline|hat)\b/, "\\tex"],
    [/(^|\n)#{1,4} /, "# titolo"], [/<\/?(br|span|div|sup|sub|img)\b/i, "<tag>"],
    [/&(nbsp|amp|lt|gt);/, "&entity;"], [/`[^`\n]+`/, "`code`"], [/\[@[a-z]/i, "[@cit]"],
  ];
  async function waitImgs(s) {
    const imgs = [...s.querySelectorAll("img")];
    await Promise.all(imgs.map((i) => i.complete ? null : new Promise((r) => { i.addEventListener("load", r, { once: true }); i.addEventListener("error", r, { once: true }); setTimeout(r, 3000); })));
  }
  function measure(s, label) {
    const sc = Reveal.getScale() || 1;
    const sr = s.getBoundingClientRect();
    let bottom = 0, right = 0, worst = null;
    s.querySelectorAll("*").forEach((e) => {
      if (e.closest(".countdown, aside.notes, .speaker-notes")) return;
      const cs = getComputedStyle(e);
      if (cs.display === "none" || cs.position === "fixed") return;
      const r = e.getBoundingClientRect();
      if (!r.height || !r.width) return;
      const b = (r.bottom - sr.top) / sc, rt = (r.right - sr.left) / sc;
      if (b > bottom) { bottom = b; }
      if (rt > right) { right = rt; worst = e; }
    });
    const issues = [];
    if (bottom > LIMIT + 2) issues.push("fondo +" + Math.round(bottom - LIMIT) + "px");
    if (right > W + 4) issues.push("destra +" + Math.round(right - W) + "px (" + worst.tagName.toLowerCase() + (worst.className && typeof worst.className === "string" ? "." + worst.className.split(" ")[0] : "") + ")");
    s.querySelectorAll("pre").forEach((p) => {
      if (p.offsetParent && p.scrollWidth > p.clientWidth + 2) issues.push("codice largo +" + (p.scrollWidth - p.clientWidth) + "px");
      if (p.offsetParent && p.scrollHeight > p.clientHeight + 2) issues.push("codice alto +" + (p.scrollHeight - p.clientHeight) + "px");
    });
    return issues.map((i) => label + ": " + i);
  }
  function textChecks(s, label) {
    const c = s.cloneNode(true);
    c.querySelectorAll("pre, code, script, style, math, .countdown, aside.notes, svg").forEach((e) => e.remove());
    const t = c.textContent;
    const issues = [];
    for (const [re, name] of raw) { const m = t.match(re); if (m) issues.push(label + ": sintassi " + name + " «" + m[0].slice(0, 40).replace(/\s+/g, " ") + "»"); }
    s.querySelectorAll("img").forEach((i) => { if (i.complete && i.naturalWidth === 0) issues.push(label + ": immagine rotta " + (i.getAttribute("src") || "").slice(0, 60)); });
    s.querySelectorAll("merror").forEach((m) => issues.push(label + ": merror «" + m.textContent.slice(0, 40) + "»"));
    if (s.querySelector("mjx-container, .MathJax")) issues.push(label + ": MathJax presente");
    return issues;
  }
  const slides = Reveal.getSlides();
  for (const s of slides) {
    const ind = Reveal.getIndices(s);
    Reveal.slide(ind.h, ind.v, 0);
    await sleep(120);
    await waitImgs(s);
    await sleep(80);
    const title = ((s.querySelector("h1, h2, h3") || {}).textContent || "").trim().slice(0, 40);
    const label = "#" + (ind.h + 1) + (ind.v ? "." + ind.v : "") + " " + title;
    // mostra tutti i frammenti, come a fine slide
    s.querySelectorAll(".fragment").forEach((f) => f.classList.add("visible"));
    out.push(...textChecks(s, label));
    const tabsets = [...s.querySelectorAll(".panel-tabset")];
    if (!tabsets.length) { out.push(...measure(s, label)); continue; }
    for (const ts of tabsets) {
      const links = [...ts.querySelectorAll(".panel-tabset-tabby a, .nav-tabs .nav-link")];
      for (const a of links) {
        a.click();
        await sleep(100);
        await waitImgs(s);
        out.push(...measure(s, label + " [" + a.textContent.trim().slice(0, 20) + "]"));
      }
      if (links[0]) links[0].click();
    }
  }
  Reveal.slide(0, 0, 0);
  return { slides: slides.length, issues: out };
}
