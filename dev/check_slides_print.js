// Uso: aprire docs/slides/0N-*.html?print-pdf in Chrome e lanciare questa funzione
// con evaluate_script di chrome-devtools MCP (sourcePath). Le slide su più pagine
// sono attese dove ci sono le schede; «tagliato» indica contenuto sul piè di pagina.
async () => {
  // Controllo della modalità stampa (?print-pdf): pagine per slide, contenuto
  // tagliato oltre pdf-max-pages-per-slide, schede tutte visibili col titolo.
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  for (let i = 0; i < 50 && !document.querySelector(".pdf-page"); i++) await sleep(200);
  await sleep(1500);
  const cfg = Reveal.getConfig();
  const pages = [...document.querySelectorAll(".pdf-page")];
  const H = pages.length ? pages[0].getBoundingClientRect().height : 0;
  const pageH = Math.min(...pages.map((p) => p.getBoundingClientRect().height));
  const out = [];
  let total = 0;
  pages.forEach((p, k) => {
    const s = p.querySelector("section");
    const ph = p.getBoundingClientRect().height;
    const n = Math.round(ph / pageH);
    total += n;
    const title = ((s && s.querySelector("h1, h2, h3")) || {}).textContent || "";
    const label = "p" + (k + 1) + " " + title.trim().slice(0, 35);
    // contenuto oltre la pagina (o le pagine) assegnata alla slide
    if (s) {
      const top = p.getBoundingClientRect().top;
      let bottom = 0;
      s.querySelectorAll("*").forEach((e) => {
        if (e.closest(".countdown, aside.notes")) return;
        const r = e.getBoundingClientRect();
        if (r.height && r.width) bottom = Math.max(bottom, r.bottom - top);
      });
      if (bottom > ph - 50) out.push(label + ": tagliato, contenuto " + Math.round(bottom) + "px su " + Math.round(ph) + " (" + n + " pag.)");
      // nelle slide delle mappe l'indice si nasconde apposta (statmed.scss)
      if (!s.classList.contains("mappa")) s.querySelectorAll(".panel-tabset").forEach((ts) => {
        const panes = [...ts.querySelectorAll(":scope > .tab-content > div")];
        const hidden = panes.filter((d) => getComputedStyle(d).display === "none").length;
        const titled = panes.filter((d) => d.querySelector(":scope > .tab-print-title")).length;
        if (hidden || titled < panes.length) out.push(label + ": schede " + panes.length + ", nascoste " + hidden + ", con titolo " + titled);
      });
    }
    if (n > 1) out.push(label + ": " + n + " pagine");
  });
  return { slides: Reveal.getSlides().length, pdfPages: pages.length, printedPages: total, pageH: Math.round(pageH), maxPages: cfg.pdfMaxPagesPerSlide, issues: out };
}
