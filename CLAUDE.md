# statistica-medica-short

Portale Quarto dei corsi di Statistica Medica per le Professioni Sanitarie (UniPD). Il sito si genera in `docs/` e lo pubblica GitHub Pages; le slide sono xaringan (`slides/*.Rmd`, con gli `.html` già compilati e copiati così come sono).

## Ancoraggio

| voce | valore |
|---|---|
| commit | automatici, deciso il 2026-11-09; il push lo fa [cl] |

## Convenzioni

- Ogni modifica ai sorgenti si committa insieme al render di `docs/` (`quarto render` dalla radice).
- Una pagina per corso e anno in `corsi/<anno>_<cdl>_<sede>.qmd`, linkata dal menu «CdL» di `_quarto.yml`; il link Moodle del corso è `bit.ly/<cdl>-<aa>-moodle`.
- Il calendario delle lezioni nelle pagine dei corsi resta generale (una voce per ambito, senza dettagli fra parentesi), come in `corsi/2026_ortottica_padova.qmd`.
- Le larghezze delle colonne della tabella (15/70/15) stanno nel front matter (`tbl-colwidths`), non nella riga `: {tbl-colwidths=...}` sotto la tabella: l'editor visuale di RStudio quella riga la cancella.
