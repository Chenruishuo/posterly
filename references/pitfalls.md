# Preventive rules shared across templates

Read [Universal pitfalls](#universal-pitfalls) before authoring any template and when checking the result. Read [Layout-shared pitfalls](#layout-pitfalls) before authoring or fixing the corresponding column/header/banner/tile/footer layout. These remain authoring obligations, not merely troubleshooting suggestions.

See [scaffold BASE DEFENSES](design-workflow.md#scaffold), [measurement](validation.md#measure-loop), and [visual Gates A–G](visual-polish.md) for the referenced fixes and contracts.

[Shared reading and path rules](../SKILL.md#reading-contract-and-execution-boundaries) apply.

<a id="universal-pitfalls"></a>

<!-- preserved-source: SKILL.md lines 617-625 -->
## Universal pitfalls (apply to all templates)

1. **`<` raw in MathJax inline** → may be HTML-parsed before MathJax sees it (mode-dependent). Prefer `\lt` everywhere. Preflight catches `(?<!\\)<(?![=/!])` inside `$…$` / `$$…$$` / `\(…\)` / `\[…\]` — i.e. raw `<` NOT preceded by a backslash and NOT followed by `=` / `/` / `!`. The `<=` case is intentionally exempt (single MathJax token, parsed atomically — no HTML-tokenizer ambiguity); preflight stays quiet about it, but `\le` reads more naturally in print.
2. **`\ ` (backslash-space) from LaTeX** → renders literally. Strip when porting from `.tex`. Preflight catches.
3. **Screen-mode measurement is misleading.** Always use `tools/poster_check.py measure` — never eyeball the screen render.
4. **Pre-compact `\\ ` and lone `<`** — preflight catches before render.
5. **`text-wrap: balance` needs Chromium ≥ 114** — Playwright's bundled Chromium is fine.
6. **`text-transform: uppercase` silently corrupts math symbols.** Lowercase Greek carries an uppercase mapping — an `α` inside an uppercased eyebrow / heading / display word renders as `Α`, glyph-identical to Latin `A` in most faces (`SHARPEN α>1` prints as `SHARPEN A>1`); the micro sign does it too (`5 µs` prints as `5 ΜS`). The HTML source stays correct, so nothing but the rendered sheet shows it. Never let a math symbol inherit an uppercase transform: wrap it in the templates' `.tt-none` utility span (ships in BASE DEFENSES — carry it into custom sheets) or drop the transform on that element. `polish` flags rendered occurrences as `SYMBOL-CASE`.

<!-- end-preserved-source: 617-625 -->

<a id="layout-pitfalls"></a>

<!-- preserved-source: SKILL.md lines 626-637 -->
## Layout-shared pitfalls (column-based templates)

7. **`overflow: hidden` on `.body-grid` clips card shadows.** If last card sits at body-grid bottom, its 30-px shadow is cut and visually merges into the strip below.
8. **`padding-bottom` on `.column` does NOT push cards down** (cards stack from the top in flex; column padding only reserves space below). But `padding-bottom` on the **last card** *does* raise that column's bottom — `measure` reads the card's border-box bottom — so it's the one continuous, zero-reflow lever for a sub-line alignment residual (see [Step 4 fine-tuning levers](validation.md#fine-tuning-levers)). Don't confuse the two; to shrink a column, edit card content directly.
9. **Title-block can dominate header height.** Shrinking logos/QR doesn't help if `.title-block` is already the tallest cell.
10. **Banner can grow from `.banner-stats`.** Big numbers cascade into body-grid shrinkage.
11. **`box-shadow: 0 2u 6u` extends ~30 px** below the card. Final last-card-bottom must be ≥ 30 px above the strip below.
12. **Image-left + text-right inside a narrow column wastes the image.** For wide images in narrow cols, keep image-on-top + caption-below.
13. **Title: prefer one line.** Size the title from the `--fs-*` scale so it fits the centred title track on a *single* line; accept a 2-line wrap only when one line would force an illegibly small font or break a phrase awkwardly. A gratuitous wrap costs scan-speed and first-impression impact — a one-line title reads as more finished. When it genuinely must wrap, **balance** it (`text-wrap: balance` — the shipped templates set it on `.title` in the BASE DEFENSES block; a custom masthead must carry that block itself, Step 3 item 4) so neither line is a lone word or a `*`-marked fragment (see **Gate B — lone wrapped fragment**). Priority: a clean one-liner first; a *balanced* two-liner when one line costs too much; never a ragged two-liner that strands a lone marker-prefixed word on its own line.
14. **Stat / metric tiles: vertically center content, never top-align.** A row of small tiles (`.keybox`, or a hand-rolled metric grid — e.g. tiles like `4+1 / 0 / F1·Acc·EM·mCC` where one label is far longer than the rest) stretches every tile to the tallest one; with default block flow the numbers then sit at unequal heights and read ragged in the small boxes. The shipped `.keybox .kb-item` now centers its content (`display:flex; flex-direction:column; justify-content:center`); **for any custom tile grid do the same**, so a 1-line tile's number lines up with a 2-line neighbour's instead of floating at the top.
15. **Portrait footer is narrow — keep each block to one line.** The footer is a two-block flex row (`method·venue·ack` | `code·contact`) pushed apart by `space-between`; in a sub-A1 portrait the right block's repo URL + email overflow the edge or wrap into a ragged stack — the recurring "messy bottom strip". Keep it clean: let the **QR carry the long link** and print only a short repo path (`github.com/org/repo`, no `https://`), drop a bulky `Acknowledgements:` line if it bloats the row, and lean on the shipped defaults (`flex-wrap` + `overflow-wrap:anywhere` on `.repo`) that break a long token and stack the blocks rather than overflow. If both blocks still won't fit side by side, let them stack — a clean two-line footer beats a clipped one-liner.

<!-- end-preserved-source: 626-637 -->

