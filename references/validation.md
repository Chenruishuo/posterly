# Measurement, inspection, export, and fix discipline

Any suggestion below to reselect/shrink the canvas or change the locked design direction is subject to the [confirmation policy](../SKILL.md#confirmation-policy). Reuse existing authorization for the same exact change; otherwise obtain confirmation before changing that locked choice. The existing non-interactive direction exception remains as documented.

Read [Step 4](#measure-loop), [enhanced gates](#enhanced-gates), [runner](#gate-runner), [style](#style-gate), and [fix discipline](#fix-discipline) before entering the layout loop. Read [Step 5](#visual-inspection) and [Step 6](#polish-workflow) before visual inspection/polish, and [Step 7](#final-verification) before final verification, export, or handover. The mandatory runner, check coverage, post-change revalidation, failure handling, and approvals remain required. Duplicate preflight/polish executions for an unchanged version follow the result-reuse rule below.

- [Tools and CLI inventory](#tools): consult when choosing or using a helper; optional `pack`/`fit-logos` behavior and bundle requirements remain as specified at their workflow stages.
- [Visual Gates A–G](visual-polish.md): read all sections applicable to the actual poster before authoring/inspection, and the matching section when fixing a warning. A green automated gate does not excuse the manual checks or preventive rules.
- [Universal and layout pitfalls](pitfalls.md): universal rules apply to every template; layout rules apply to the relevant layout.
- [Optional asset contract](assets.md#figure-provenance), [draft/final review](review.md), [design lock and system-extension routing](design-workflow.md#direction).

[Shared reading and path rules](../SKILL.md#reading-contract-and-execution-boundaries) apply.

<a id="result-reuse"></a>

## Reuse complete preflight/polish results for an unchanged version

A required check need not be executed a second time just because another workflow step names it. Reuse an existing **preflight** or **full standalone-polish** result only when all of the following hold:

- It belongs to the same poster version: HTML, referenced figures/logos/QR/fonts and other assets, design-token contents, any relevant manifest, and the effective check parameters are unchanged. Match actual options, including thresholds, enabled/disabled rules, and strictness, not merely the command's filename. A known tool/browser/render-environment change also invalidates the affected result. If equivalence is uncertain, run the check again.
- The corresponding check actually completed and its result and required findings remain available in the report/logs. `NOT_RUN`, early-stop `SKIPPED`, an environment failure, a missing report, or output that omits the findings needed for disposition cannot satisfy the check. A runner-level `overall: PASS` alone does not prove every check ran or every polish warning was resolved.
- `run_gates.py` executes the same `poster_check.py preflight` and `poster_check.py polish` subcommands, so their completed results qualify under these conditions. `measure --with-polish` is advisory measurement coverage and **does not replace the full standalone-polish check** or a requested strict run.
- Preserve the recorded outcome. A reused failure is still a failure; a reused warning still needs the existing fix-or-explicit-acceptance decision. Reuse never turns a failure into a pass or waives a hard gate.

After a change to those inputs/options, follow the original checking workflow again, including the complete runner after layout changes. If only a required preflight/polish result is missing for an otherwise unchanged version, execute the missing check. Use existing reports/logs and known edit history to establish reuse; no new cache, hash manifest, or bookkeeping file is required.

This rule removes duplicate preflight/polish executions only. All check types, passing thresholds, manual inspections, and Step 7 verification of the actual final PDF/exported files remain required as specified. An HTML gate report does not stand in for final-file verification.

<a id="measure-loop"></a>

<!-- preserved-source: SKILL.md lines 284-353 -->
### Step 4 — Render + measure loop (HARD GATE)

**Default driver: `run_gates.py`.** After every layout change, run the whole sequence in one shot — `preflight` → `style` → `measure` → `polish` in load-bearing order (plus the `asset` gate only when you pass `--manifest`; otherwise it's reported `NOT_RUN` and excluded from `overall`), into one `GATE_REPORT.json` (see [**Enhanced gates & fix discipline**](#enhanced-gates)):

```bash
# After every layout change (the default loop driver). The Step 2.5 pack
# (design_tokens.json, always written at lock time) rides on EVERY call —
# dropping it silently un-declares your fonts / hue centers / dark_ground:
/absolute/path/to/dedicated-env/bin/python <skill>/tools/run_gates.py poster.html --tokens design_tokens.json --report GATE_REPORT.json
```

**Before the first loop iteration — run `pack` once (advisory).** A column whose figures *at their Gate A floors* still overflow the footer-gap window — or *at their ceilings* still can't reach it — cannot be fixed by figure sizing at all, and discovering that inside the loop costs many wasted rounds. `/absolute/path/to/dedicated-env/bin/python <skill>/tools/poster_check.py pack poster.html` probes both endpoints in the browser and names the column: `REPACK_RECOMMENDED` (move a card out / trim text before looping) or `FIGURE_ONLY_UNDERFILL` (the residual needs content, not figure growth). It is advisory (exit 0; floors are polish's WARN thresholds, not physical minima; hero panels aren't modelled) — treat it as the "should I re-pack cards across columns first?" answer, then enter the loop.

**The loop is budgeted (script-enforced circuit breaker).** `measure` counts **consecutive failed measurements** in an on-disk file next to the poster (`.<filename>.posterly_budget.json`, e.g. `.poster.html.posterly_budget.json` — survives context compaction); the first PASS, 12 h idle, or `--reset-budget` clears it. At the cap (default **30**, `--measure-budget`, 0 disables) `measure` exits **3** with a `CIRCUIT BREAKER` banner and refuses to render again: stop iterating, re-think the layout (re-pack via `pack`, or reselect template/canvas) or escalate to the user with the current best state rendered — do NOT `--reset-budget` just to keep grinding the same edits. `run_gates.py` surfaces exit 3 as a measure FAIL and skips the remaining gates.

**Work from the failure report, not the file.** On a spread/gap/intercard failure, `measure` now prints (a) the **shared passing band** — the one bottom-range every column must land in — with per-column `grow/trim ~N px [safe +lo..+hi]` deltas, and (b) an **edit targets** block listing every card per column with its source line (`L<n>`), height, and a text anchor, marking the bottom card that sets the column bottom. Iterate from that report: jump to the source line or Grep the anchor, read the surrounding block to confirm you have the right card, edit, re-run. Don't re-`Read` the whole poster.html every round (the anchors are math-stripped locators, not verbatim source), and never emit the full file through your output (scaffold via `cp`, then surgical `Edit`s). Full re-reads stay legitimate where they earn their cost: first contact with an unfamiliar/custom template, a cross-column re-pack, a structural/nesting failure, an anchor that's missing or ambiguous, and the final claim audit.

This is what wires the **`style`** hard gate into every iteration — the standalone `measure` call below does **not** run `style`. posterly runs `style` with rules **4 (≤2 hue families) and 5 (no gradients) disabled by default**: the corresponding requirements must be ignored unless the respective rule is explicitly enabled; the rest of the design-system discipline stays enforced. Override with `--style-disable ''` to enforce all 14, or e.g. `--style-disable 4,5,6,7` to also drop the font rules.

The standalone `measure` call is the **minimum fallback** — a quick single-gate spot check; it skips `style`/`asset`:

```bash
# Minimum / spot-check only (no style, no asset):
/absolute/path/to/dedicated-env/bin/python <skill>/tools/poster_check.py measure poster.html
# Same single browser launch, plus the advisory polish report:
/absolute/path/to/dedicated-env/bin/python <skill>/tools/poster_check.py measure poster.html --with-polish
```

`--with-polish` runs the polish measurement on the **same rendered page** (one Chromium launch instead of two) and prints its report at default thresholds. It is **advisory there** — it never changes `measure`'s exit code; the loop's final soft gate still requires full standalone-polish coverage (`--strict` if you want it enforced). A qualifying completed runner/direct `polish` result may be reused under [result reuse](#result-reuse); this advisory `--with-polish` report alone does not qualify.

Targets (defaults; configurable via flags):
- **`spread < 5 px`** across the last-card-bottoms of all columns (+ any hero panel). Aim `< 3 px`.
- **`gap to footer-strip/footer ∈ [30, 50] px`** — card shadow visible but cards don't float.
- **`intercard gap ∈ [12, 50] px`** — whitespace between consecutive stacked cards inside a column (side-by-side cards count as one row). The ceiling catches `justify-content: space-between` faking bottom alignment on an under-filled column: spread reads ~0 and the footer gap lands in band while a void sits mid-column (observed in the wild: 98–135 px voids against a 22.7 px design row-gap). The floor catches cards packed so tight the drop shadow (`0 2u 6u` in shipped templates) is buried under the next card, fusing the stack into one slab. Tune via `--max-intercard-gap` / `--min-intercard-gap` (floor 0 to disable for shadowless themes).
- **`position align ≤ 2 px`** (authoritative) — the `[data-measure-role="poster"]` bounding box must sit at `(0, 0)` to `(viewport_w, viewport_h)` within `--position-tol-px`. This IS the full-canvas requirement: a poster whose bbox aligns to the page is necessarily full-bleed. Catches `transform: translate*`, mis-positioned `position: absolute`, stray body margin in print, and CSS source-order cascade bugs where a screen rule wins over a print override.
- **`canvas-fill ∈ [95 %, 101 %]`** (coarse early diagnostic) — `[data-measure-role="poster"]` width/height ratio against the print viewport. Fires before the position check when the ratio is FAR off, with a more diagnostic error message that points at the common `@media print { :root { --u: 1mm } }` omission (renders at ~42 %) or hardcoded `width > @page` (renders at >100 %). For borderline 95–99 % cases, position-align is the truth. Tune via `--min-canvas-fill` / `--max-canvas-fill`. **Safe-area design** belongs as internal padding on a full-bleed `.poster`, NOT as a smaller poster — a smaller poster fails position-align.
- **`content within canvas`** (hard) — the poster BOX can be exactly the right size and origin while its CONTENT is wider or taller than the canvas and gets sliced off at the page boundary — the poster box stays 24×36 in while a right (or bottom) strip of every full-width row vanishes in print. The two checks above read the poster *box*, the clip gate reads only card/column/hero/band, and the spread/gap gates read vertical bottoms, so nothing else catches this. The gate compares the poster's `scrollWidth/Height` (which includes the overflowing content in **both** overflow modes — `hidden` clips it at the poster, `visible` spills it past the page) against its client size; MathJax's 1 px-clipped a11y nodes don't inflate it. (`scrollWidth/Height` grows for overflow past the **right/bottom** edge — the direction this bug produced; content shoved off the *left/top* by a negative offset is clipped without inflating it and is NOT caught here — position-align catches a grossly displaced poster, a left-bled child inside a correctly-placed poster stays an eyeball check.) **The classic cause: a `.poster` grid with `grid-template-rows` but no `grid-template-columns` — the implicit `auto` column grows to a wide child's max-content and every full-width band overflows.** Fix: pin the column axis with `grid-template-columns: minmax(0, 1fr)` (the shipped templates now carry it in the `.poster` rule — see the *Custom skeleton? Carry the BASE DEFENSES* note in Step 3; a custom skeleton must too), or find the fixed-width child (a table, a `width:` in the wrong unit, an un-wrapped `nowrap` line) forcing the layout wide. This was a live miss: a portrait band-stack rendered its whole content at ~1.5× canvas width with `overflow:hidden` silently clipping the right third — every other gate green.

**This gate is non-negotiable.** If `measure` exits non-zero, fix the layout — do NOT continue to render. Common fixes:
- spread > 5: shrink the column with the lowest last-card by reducing a paragraph's `margin-bottom` by 1u, trimming one line, or shrinking a fixed-height figure by 5u.
- intercard gap > 50: an under-filled column is being stretched. Remove `justify-content: space-between`/`space-around` from the column, use a fixed `gap`, and absorb the slack with CONTENT (grow a figure, add paper-sourced text per Gate C) — never with whitespace. The same rule holds for **any track** — a masthead spine, side rail, or footer strip (`polish` flags those as `TRACK/INNER-VOID`; see **Slack in a track** under [Gate C](visual-polish.md#gate-c)).
- intercard gap < 12: an over-full column is being squeezed by shrinking the row-gap, which buries card shadows. Restore the design `gap` (6u ≈ 22.7 px) and take the height back out of content instead (trim a paragraph, shrink a figure by 5u, or move a card to a shorter column).
- gap > 50 everywhere: body-grid is too tall; grow a card with substance (per [Gate C / *Fill means substance*](visual-polish.md#fill-means-substance)) or reselect a smaller canvas — don't leave the whitespace.
- gap < 30 anywhere: banner/header outgrew its slot; check `.framework-banner` rendered height.
- position misaligned (the usual full-canvas failure): make `.poster` full-bleed (`width: 100%; height: 100%; margin: 0; padding: 0` in `@media print`); remove any `transform: translate*` or `position: absolute` offsets; ensure `html, body { margin: 0; padding: 0 }` in the print media query; and check that the print `@media` block comes AFTER the screen `.poster` rule so source-order cascade resolves the print override winning.
- canvas-fill < 95 % (diagnostic fired first): poster forgot `@media print { :root { --u: 1mm } }` so it renders at screen scale. Add the override.
- canvas-fill > 101 % (diagnostic fired first): hardcoded `width: 1600px` (or similar non-`--u`-based size) exceeds `@page`. Replace with `calc(N * var(--u))`.
- content overflows the canvas (right/bottom strip sliced off): the `.poster` grid is missing `grid-template-columns` — add `grid-template-columns: minmax(0, 1fr)` so the single content column can't grow past the canvas; or hunt the fixed-width child (table, wrong-unit `width:`, `nowrap` line) forcing the layout wide.

<a id="fine-tuning-levers"></a>

**Fine-tuning levers — continuous vs. quantized.** The fixes above move height in ~one-line jumps; the last few px to reach `spread < 5` need a *continuous* lever, and not every knob is one:
- **Figure width is continuous only when the figure is the column's bottom-most element** — a centered/stacked figure, or a float tall enough that text never extends below it. In a float-*wrap* where text flows *below* the figure, widening it toggles whole text lines (one session: 48 % → 2823 px, 51 % → 3351 px — a 528 px jump for +3 %) and in the text-dominated regime it does nothing at all. Don't use figure width for sub-line alignment there.
- **For a sub-line residual, add `padding-bottom` to the column's *last card*** — continuous and zero-reflow (text doesn't re-wrap), and `measure` reads the card's border-box bottom so it raises the column cleanly. Lever of last resort, *only* for a < ~1-line residual on a normal-flow, auto-height last card (a `flex:1` / fixed-height card won't grow this way). A *large* padding-bottom is a Gate-C smell, not this — it will (and should) trip `CARD/TRAILING`; fill big gaps with real content instead.
- **`line-height` set on a `.card` won't reach its text** — `.card p` / `.card li` carry their own `line-height` (higher specificity), so it silently no-ops. Override the text elements directly if you must compress line spacing.

`poster_check.py measure` also has these safety nets (so a false PASS shouldn't happen):
- Missing `[data-measure-role="poster"]` = hard fail.
- Empty columns = hard fail (override: `--allow-empty-column`).
- Missing footer-strip AND footer = hard fail (override: `--allow-no-footer-gap`).
- MathJax intended (a `<script src="…mathjax…">` tag or `window.MathJax` config is present) but no `<mjx-container>` rendered, while TeX delimiters (`$…$` / `$$…$$` / `\(…\)` / `\[…\]`) remain in body text = hard fail (CDN block, script error). A page that just *describes* TeX syntax in prose without ever loading MathJax is NOT failed.
- MathJax typeset timeout = hard fail (override: `--mathjax-timeout-ms`).
- `@page` size missing AND no `--canvas` override = exit 2.

If a completed preflight result already covers the unchanged version under [result reuse](#result-reuse), reuse it instead of running it again. Otherwise, run preflight in parallel as before:

```bash
/absolute/path/to/dedicated-env/bin/python <skill>/tools/poster_check.py preflight poster.html
```

Catches: LaTeX residue (`\ref{`, `\cite{`, `\textbf{`, lone `\ `), bare `<` inside `$…$` math (MathJax mis-parses as HTML tag), missing local images, missing `data-measure-role="poster"`, unknown role values.

<!-- end-preserved-source: 284-353 -->

<a id="visual-inspection"></a>

<!-- preserved-source: SKILL.md lines 354-373 -->
### Step 5 — Render + visual inspection

```bash
/absolute/path/to/dedicated-env/bin/python <skill>/tools/render_preview.py poster.html
pdftoppm -r 150 poster_preview.pdf poster_check -png -f 1 -l 1
# then Read the resulting PNG
```

For dense regions, crop with PIL and read the slice — full poster at r=150 is ~9000 px wide; useful regions (header, banner, takeaways, one column) at full res reveal text wrapping issues invisible in the thumbnail.

Two checks that need the *card-level* crop, and that generic "look at the render" reliably misses (both shipped on a real poster whose agent had read the figures closely enough to caption them):
- **Track bottoms, per card.** For every card whose content splits into side-by-side columns, compare the columns' content bottoms and the leftover air at each column's foot. The `CARD/TRACK-MISALIGN` gate covers `.track`-classed columns above its threshold; the eyeball covers what it can't — unclassed columns, and borderline offsets around ~6 mm that read ragged in context (fix order in Gate C).
- **Figure edges, all four.** For every raster figure, check no edge cuts through glyphs, axis labels, legends, or lines — a crop that landed a few px short slices content in a way no automated gate can distinguish from a legitimately tight crop. For a matched figure group, additionally confirm the panels render at the same height (unequal heights on equal-width mounts = mismatched crop geometry; see `FIG/PAIR-GEOMETRY`).

**Never judge typography from a raster below 150 DPI** (150 is also pdftoppm's own default; the old `-r 100` here was below it). The rasterizer rounds every glyph advance to a whole pixel, so low-DPI body text picks up uneven letter spacing that does not exist in the PDF. Measured on a 24×36 poster at 12 pt body: at r=100, 4 of 26 letter pairs merged into single blobs and the tightest gap read 0.72 pt against a true 1.20 pt; by r=150 every pair separates again, though the gaps only converge on their true widths by r=300. So r=150 is the working floor — good for layout, wrapping, overflow, and for the Step 7 deliverable — but if you need to adjudicate a fine kerning or letter-collision question, re-render that region at r=300 or read the PDF. Never take a typography verdict from the thumbnail or a 100-DPI render.

Beyond defect-hunting, hold the render against its own `DESIGN DIRECTION` block once: at thumbnail size the locked hero moment should be the first place the eye lands (a competing loud element is a quiet-it fix in Step 6, not a redesign), and the sheet should still read as its concept statement rather than as parts from different posters.

**Identity mark — check it by eye.** On the same render, crop the bottom-right corner and confirm the `⊕` corner-signature actually PAINTS: a crisp ring + crosshair at glyph scale, visible against its ground (add `on-dark` on dark grounds). If a woven `⊕` is placed, confirm it reads as a small inline glyph riding its host — not a blown-up block, not a blank gap. On an anonymous poster (`data-ps-identity="off"`), the same look must confirm **no** `⊕` anywhere. The gates verify *structure*, not *paint* — a stray style on the `<use>`, an exotic SVG nesting, or a deformed glyph can pass every static check while rendering wrong or blank — so this eyeball is the paint-level gate. A missing/blank/distorted `⊕` means the sprite or mark markup drifted: restore it verbatim from a template before Step 6.

<!-- end-preserved-source: 354-373 -->

<a id="polish-workflow"></a>

<!-- preserved-source: SKILL.md lines 374-388 -->
### Step 6 — Polish

After alignment is solid, inspect the **visual polish gate** result. Reuse an existing completed standalone-polish result from the runner or a direct call only under [result reuse](#result-reuse); otherwise run the gate:

```bash
/absolute/path/to/dedicated-env/bin/python <skill>/tools/poster_check.py polish poster.html
```

This is a **soft** gate (exits 0 by default; pass `--strict` to fail on warnings). It surfaces failure modes that the hard alignment gate cannot see — figure sizing relative to its aspect ratio, typography orphans, column whitespace pretending to be balance, `<br>`-in-flex collapse, and header-logo problems (broken / oversized / QR-height mismatch / title squeeze). See [**Visual polish gates**](visual-polish.md#visual-gates) for the rule for each WARN class and the correct fix. Fix every WARN unless you explicitly judge it acceptable for this poster.

Other polish:
- **`text-wrap`** — match the property to the text:
  - **`balance`** only on **short, centered** display text (titles, captions, one-line takeaways ≤ 2 lines); it evens the ragged edge.
  - **Never `balance` on multi-sentence prose** (banner TL;DR, long takeaways), and especially not with `text-align: left`. Near a 2↔3-line threshold, balance shortens and hyphenates the **first** line to "even" the block, producing a crammed-left / big-gap-right banner. For prose that should fill its box, use **`text-wrap: pretty`** (fills each line, only protects the last-line orphan) or plain natural wrap.

<!-- end-preserved-source: 374-388 -->

<a id="final-verification"></a>

<!-- preserved-source: SKILL.md lines 398-437 -->
### Step 7 — Final verification

```bash
/absolute/path/to/dedicated-env/bin/python <skill>/tools/poster_check.py verify-final poster_preview.pdf \
    --canvas 60x36in --max-size-mb 20
# or read the expected canvas from the companion HTML:
/absolute/path/to/dedicated-env/bin/python <skill>/tools/poster_check.py verify-final poster_preview.pdf \
    --from-html poster.html
```

Checks: page count == 1, dimensions match canvas, file size ≤ limit. `--canvas` accepts inch dimensions (`60x36in`) or named sizes (`A0 portrait`, `A1 landscape`). By default rejects swapped W/H unless the PDF declares `Page rot ∈ {90, 270}` or you pass `--allow-rotated`. `--from-html <path>` reads `@page { size: … }` from the HTML so they can't drift apart.

**Then export the deliverable PNG — 150 DPI, same resolution as the Step 5 render:**

```bash
pdftoppm -r 150 -singlefile -png poster_preview.pdf poster   # -> poster.png
```

The PDF is the print artifact; the PNG is what gets dropped into slides, chats, and web pages. 150 is the floor that clears the letter-merging threshold from Step 5 — at 12 pt body every letter pair separates again — and it is deliberately no higher: it keeps a 60×36 canvas at 9000×5400 (49 MP), fast to rasterize and openable everywhere. `-singlefile` is what makes the output `poster.png` rather than `poster-1.png`.

Never hand over `*_preview.png` (a 0.35× thumbnail, ~34 DPI) as the deliverable. The Step 5 inspection render is the same resolution as this export, so reuse it rather than rasterizing twice if it is still on disk — just make sure the delivered file is named `poster.png`.

Raise the DPI only for a small canvas meant to be read close up, and know the ceiling: 300 DPI on a 60×36 is 194 MP, which trips PIL's default `MAX_IMAGE_PIXELS` guard (~179 MP) with a `DecompressionBombError` and takes minutes to rasterize.

**Then, whenever the HTML itself is handed over — bundle it.** `poster.html` is only half a poster: it resolves `images/`, any vendored `fonts/`, and the MathJax CDN *relative to the working directory*. Sent on its own it opens as alt-text boxes in fallback faces, and the recipient cannot re-render it. So if the handover includes the source (a co-author who will edit it, a print shop, a customer who paid for an editable file), ship the bundle, not the raw file:

```bash
/absolute/path/to/dedicated-env/bin/python <skill>/tools/poster_check.py bundle poster.html -o poster_standalone.html
```

Every local reference becomes a `data:` URI and MathJax becomes inline script text: one file, no network, still fully editable — the recipient edits the prose or the CSS and re-renders with `render_preview.py` to get the same sheet back. It hard-fails rather than write a bundle that still points outside itself, so a non-zero exit means a reference you need to localize first, not a warning to wave through. Keep `poster.html` as the working file — never bundle over it (the command refuses), and don't re-enter the measure loop on a multi-MB bundle. Deliver `poster_standalone.html` under whatever name the recipient expects.

Then report to the user:
- File path of PDF and of the 150-DPI PNG
- Final spread (px) and gap-to-footer range
- Any unresolved Codex feedback
- Page-fit confirmation

**Upstream feedback (default behavior).** If the run surfaced a defect or rough edge in posterly itself — a gate false positive/negative, a template bug, a misleading instruction, a tool crash you worked around — keep a note of it during the run, and after delivering the poster ask the user whether to open an issue or PR against the posterly repo (https://github.com/Chenruishuo/posterly). Bring the specifics (exact gate output, minimal repro, or proposed patch); file nothing without the user's go-ahead.

<!-- end-preserved-source: 398-437 -->

<a id="tools"></a>

<!-- preserved-source: SKILL.md lines 648-677 -->
## Tools

```
tools/
├── poster_check.py        ← CLI: measure / pack / fit-logos / preflight / polish / verify-final
├── render_preview.py      ← CLI: print-emulated PDF + thumbnail PNG
├── run_gates.py           ← orchestrator: preflight→style→asset→measure→polish → GATE_REPORT.json   (vendored, ARIS)
├── style_check.py         ← HARD style gate: token-only colors, no inline style, font/size scale     (vendored, ARIS)
├── asset_check.py         ← real-figure provenance gate (data-source + FIGURE_MANIFEST)               (vendored, ARIS)
├── extract_pdf_figures.py ← pull real figures from a paper PDF (contact-sheet / auto / crop)          (vendored, ARIS)
├── preprocess_figures.py  ← autocrop / resolution-check crops, keep the manifest honest               (vendored, ARIS)
└── _posterly/             ← internal modules (canvas parser, Playwright + settle, etc.)
```

The five `(vendored, ARIS)` tools are documented in [**Enhanced gates & fix discipline**](#enhanced-gates) (license/attribution in `NOTICE.md`); they reuse posterly's own `_posterly` engine. The **minimal fallback** uses only `poster_check.py` + `render_preview.py`:

- `poster_check.py`:
  - `measure` — **hard** geometry gate (column-bottom spread < 5 px, gap-to-footer in [30, 50] px, intercard gap in [12, 50] px inside each column, canvas-fill ∈ [95 %, 101 %] as a coarse diagnostic, poster bbox aligns to the page within ±2 px — the bbox-alignment check is the authoritative full-canvas requirement — poster *content* stays within the canvas box, catching a right/bottom strip sliced off when content overflows a mis-configured `.poster` grid, and content that escapes a card does not collide with a neighbouring card/banner/header beyond `--max-collision-px` (default 3 px)). On failure prints the shared passing band + per-column safe deltas and the edit-targets block; carries the consecutive-failure circuit breaker (exit 3 at the budget cap). `--with-polish` folds the polish measurement onto the same rendered page (advisory report; measure's exit code untouched) — one browser launch when a round wants both readings.
  - `pack` — **advisory** column-feasibility pre-check (run once before the loop): probes card figures at their Gate A band endpoints in-browser and reports columns unreachable by figure sizing alone.
  - `fit-logos` — **advisory, read-only** logo-zone packer (ported from ResearchStudio's paper2poster, reshaped for the human-in-the-loop idiom: it never edits the file). Measures the header logo zone (an explicit `--zone` selector overrides everything and never falls back; else `[data-logo-zone]`; else the *union* of `data-lf-h0`-stamped zones, `.logo-row`s, and standalone `.logo-slot`s, with nested candidates resolved stamp > row > slot and outer winning ties — rows/slots *inside* an applied `logo-pack` are never auto-discovered, so a re-run returns to the original zone, and a poster with one applied and one untouched zone keeps both), searches row partitions for the arrangement that maximises the ONE uniform height every institution mark shares, and prints the proposal — rows, per-mark widths, opaque-pixel fill, a paste-ready snippet — plus a note when that height would trip Gate E's QR match. **Use it critically**: the packer equalizes *bounding boxes* only; optical weight (a dense lockup beside a clean wordmark, [Gate E](visual-polish.md#gate-e)) is an authoring judgment it cannot make. Apply the snippet by hand only if it reads right in the preview, adapt it (e.g. swap to size classes or a width-normalized `logo-stack`), or ignore it and place the logos yourself — then re-run the gates either way. Most useful at ≥3 marks of mixed AR; for one or two logos the size classes are already the answer. **Re-run idempotency:** when you apply a proposal into a content-sized zone, also stamp the zone's pre-application height as `data-lf-h0="<px>"` (the CLI prints the exact stamp line) — an applied pack collapses the zone to its packed height, so an unstamped re-run measures only the shrunken strip and can only propose smaller; the advisor reads the stamp back (`max(stamp, live box)`, so a template-grown zone still wins) and warns when it finds an applied pack without one.
  - `preflight` — static HTML lint (LaTeX residue, math `<`, missing images, role validation, `.figure` blocks missing their one-line `.caption`).
  - `polish` — **soft** visual gate (figure sizing by AR, broken images, typography orphans, space-between fill, card trailing / mid-card voids, `<br>`-in-flex collapse, header logos: broken / oversized / QR mismatch / title squeeze). Warns by default; `--strict` to fail. Hard-fails if the poster has no `[data-measure-role]` markup at all (silent PASS would be a worse bug). Its measurement half also rides `measure --with-polish` (same rendered page, advisory there); full standalone-polish coverage remains the loop's final soft gate, with an unchanged-version result reusable under [result reuse](#result-reuse).
  - `verify-final` — `pdfinfo`-based PDF sanity (page count, dimensions, file size).
  - `bundle` — freeze the poster into ONE self-contained HTML for handover: local `src=` / CSS `url()` (images, vendored fonts) become `data:` URIs and the MathJax CDN `<script>` becomes the skill's own bundled `tex-svg.js`, inline. Hard-fails rather than write a file that still points outside itself. Run last, on a green poster, and never over the workspace copy.
- `render_preview.py` — Playwright print-emulated PDF + scaled PNG thumbnail.

All scripts read `@page { size: W H }` from the input HTML so the same code handles ICML 60×36 landscape, ICLR 24×36 portrait, CVPR A0, etc. without flags.

Every gate render also serves MathJax from the skill's **bundled copy** (`assets/mathjax/tex-svg.js`, MathJax 3.2.2 — the renderer intercepts the templates' CDN request), so math typesetting during measurement is deterministic and offline-safe; a hand-opened `poster.html` still loads from the CDN as before.

<!-- end-preserved-source: 648-677 -->

<a id="enhanced-gates"></a>

<!-- preserved-source: SKILL.md lines 678-681 -->
## Enhanced gates & fix discipline (vendored from ARIS)

These tools and the fix discipline below are vendored from ARIS's `paper-poster-html` (MIT © 2026 wanshuiyin — see `NOTICE.md`). They layer on top of the Step 4 / Step 6 gates and reuse posterly's own `_posterly` engine. For a poster scaffolded from posterly's own templates they are the **default loop, not extras**: `run_gates.py` is the Step 4 driver and `style` is a hard gate every iteration (`asset` stays opt-in via `--manifest`). The bare `poster_check.py` core (preflight / measure / polish / verify-final) is the **fallback** only for a non-tokenized or imported template that can't pass `style` — it is *not* a license to skip `style` on a poster built from these templates.

<!-- end-preserved-source: 678-681 -->

<a id="gate-runner"></a>

<!-- preserved-source: SKILL.md lines 682-697 -->
### One-shot gate runner — `run_gates.py`

Instead of calling `measure` / `preflight` / `polish` by hand each iteration, run all gates in their load-bearing order and get the whole fix surface in one report:

```bash
# core gates (preflight + style + measure + polish); --tokens carries the
# Step 2.5 pack (design_tokens.json, always written at lock time):
/absolute/path/to/dedicated-env/bin/python tools/run_gates.py poster.html --tokens design_tokens.json --report GATE_REPORT.json
# add --manifest to also run the real-figure asset gate (references/assets.md#figure-provenance):
/absolute/path/to/dedicated-env/bin/python tools/run_gates.py poster.html --tokens design_tokens.json --manifest FIGURE_MANIFEST.json --report GATE_REPORT.json
```

Order is fixed: `preflight → style → asset → measure → polish`.

- **Default: accumulate results.** A failed gate does not by itself stop the runner; it continues through the remaining enabled gates, including later renders, and collects their results.
- **`--fail-fast`: stop at the first hard failure.** This includes a hard gate that could not run because of an environment error; under `--strict-polish`, a polish failure also counts as hard. Remaining gates are recorded as `SKIPPED`.
- **Circuit-breaker exception:** `measure` exit 3 always stops the remaining gates, whether or not `--fail-fast` is set. The report retains the measure failure and records the remaining gates as `SKIPPED`.

Continuing to collect results does not clear an earlier failure: any hard failure keeps `overall` at `FAIL`. `GATE_REPORT.json` holds each gate's status and available findings; early-stopped gates are not reported as passed. Child processes run with `sys.executable`, so it uses the same interpreter/venv as posterly. By default `run_gates.py` forwards `--style-disable 4,5` to the style gate (posterly's default — see [**Style HARD gate**](#style-gate) for what that drops and how to re-enable). Plain `poster_check.py measure` still works if you don't adopt the style/asset gates.

Without `--manifest`, the asset gate is **opt-in** — it is reported `NOT_RUN` and excluded from `overall` (real figures not verified), so a green `overall` means *the gates that ran* passed, not that figures were checked. (This is a posterly fix to the vendored orchestrator — see `NOTICE.md`; upstream silently counted the missing-manifest asset gate as a pass.)

<!-- end-preserved-source: 682-697 -->

<a id="style-gate"></a>

<!-- preserved-source: SKILL.md lines 698-713 -->
### Style HARD gate — `style_check.py`

The Step 6 `polish` gate is *soft* (aesthetics). `style_check.py` is a **hard** gate for the design-system discipline the templates assume:

```bash
/absolute/path/to/dedicated-env/bin/python tools/style_check.py poster.html --disable 4,5 --tokens design_tokens.json   # posterly default; the pack is always written at lock time (Step 2.5)
```

14 rules: colors only via `var(--…)` from the `:root` token block (no stray hex), no inline `style=`, the two-hue-family limit only when rule 4 is enabled, gradient restrictions only when rule 5 is enabled, font-family against a whitelist, font-size only from the `--fs-*` scale, bounded token count, the `data-*` / inline-SVG contracts, (rule 13) every `block--modifier` variant class used in the markup must have a matching CSS rule, and (rule 14) every numeric utility class used (`w-65`, `mt-2`, `sr-46`) must have one too — an undefined width utility lets the figure render at natural size and balloon its column (three wave-2 posters hit exactly this) — a dropped rule leaves the class inert and the layout silently wrong (e.g. a `keybox--4` with no `.keybox.keybox--4` rule falls back to the 3-col base grid, orphaning a 4th tile into an empty second row). Pure static analysis plus a small Playwright render gate for computed-style rules, so it's cheap — run it right after the Step 3 scaffold and on every layout change.

**posterly default — rules 4 and 5 are disabled** (`run_gates.py` forwards `--style-disable 4,5`): rule 4 (≤2 non-neutral hue families) and rule 5 (gradient restrictions) apply **only when the respective rule is explicitly enabled**. When a rule is disabled, **ignore its corresponding requirements everywhere**, including component anti-patterns and recommended catalog conventions. Do not restrict hue count or remove gradients to satisfy a disabled rule, and do not treat its computed findings as defects requiring a fix. The other 12 — the *operational* discipline: token-only colors, no inline `style=`, the font/size scale, the data-attribute and variant-class contracts — stay enforced. A disabled rule still runs and shows in the report as `SKIPPED`; it just no longer drives pass/fail. Calling `style_check.py` directly enforces all 14 unless you pass a disable list, so always preserve the current poster's explicit rule choices when switching between the runner and standalone tool; a tool default is not a reason to silently enable a rule. With neither rule enabled, use `--style-disable 4,5` (the runner default) or standalone `--disable 4,5`. To enable only rule 4, disable `5`; to enable only rule 5, disable `4`; to enable both, pass an empty disable list (`--style-disable ''` on the runner or `--disable ''` standalone). Preserve any other explicitly configured rule switches. Disabled-rule notes do not override independent token-only color, contrast, structure, or readability requirements.

> **Note.** `style_check` assumes a *tokenized* template — a `/* ===== DESIGN TOKENS ===== */ … /* ===== END DESIGN TOKENS ===== */` block, colors via `var(--…)`, sizes via `--fs-*`, no inline `style=`. The hue-count and gradient restrictions apply only when style rules 4 and 5 respectively are enabled; ignore each when disabled. posterly's `*_neutral.html` templates **are** tokenized (vendored from ARIS — see `NOTICE.md`), so a poster scaffolded from them passes `style` out of the box. A hand-written or imported non-tokenized template will FAIL `style` until you tokenize it; the other gates (`preflight` / `measure` / `polish`) don't require tokenization.

> **Reconciling with the older layout examples.** Some examples in [*Step 6 / Visual polish gates*](visual-polish.md#visual-gates) set figure widths with inline `style="width: …"`. `style_check` (rule 2) forbids inline `style=` **except** `style="width: NN%"` on an `img[data-source="paper"]` and anything inside a `data-color-exempt="logo"` element. So if you adopt `style_check`, express figure widths via the `w-95` / `w-100` utility classes (see `templates/COMPONENTS.md`) or a tokenized component rule rather than taking the bare inline-`style=` snippets literally — and size logos by their size class or a tokenized variant (Gate E), never a bare inline height on the slot.

<!-- end-preserved-source: 698-713 -->

<a id="fix-discipline"></a>

<!-- preserved-source: SKILL.md lines 725-733 -->
### Fix discipline — softened closed-set fix vocabulary

The failure mode of any "render → review → fix → re-render" loop is the **patch loop**: the agent fixes one nit by adding an inline style / a new hex / a one-off SVG, the next gate flags *that*, and it never converges. The discipline below keeps the Step 6 loop bounded. It is the **softened** form of ARIS's closed set — half-closed, with a smooth escape hatch — suited to posterly's human-in-the-loop use:

- **Prefer the named knobs.** Every fix inside the loop should be one of the 7 operations catalogued in `templates/COMPONENTS.md` (edit a `:root` token; swap/add/remove a catalogued component; rebalance paper-sourced content; reselect template/canvas; edit a component's token-only CSS; toggle a predefined variant; fix an asset). These are *named, reusable* knobs, not one-off hacks.
- **No one-off hacks.** No new inline `style=`, no new hex anywhere (colors come from tokens), no bespoke decorative SVG, no single-element font-size override — `style_check.py` enforces these as hard rules.
- **Escape hatch (the softening).** If a fix genuinely needs something outside the catalog — a new token, variant, or component — the agent may **propose** it explicitly, flagged as a *system extension* for your review, rather than being hard-blocked. On approval, add it to `COMPONENTS.md` / the token block and re-run from Step 3 so it passes `style` from a clean state. Don't splice a new element into a mid-loop poster silently.
- **Round caps are a guide, not a wall.** Default: ≤3 issues per round, and after ~3 rounds without reaching your visual bar, stop patching and escalate (reselect template/content, or a human call) rather than endless cosmetic micro-tuning. Adjust the caps deliberately — you're in the loop.

<!-- end-preserved-source: 725-733 -->

