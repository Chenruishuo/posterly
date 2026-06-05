---
name: posterly
description: "Build an academic conference poster (ICML/NeurIPS/ICLR/CVPR/etc.) as a single HTML/CSS file and render it to print-ready PDF via headless Chromium. Use when user says \"做海报\", \"poster\", \"ICML/NeurIPS/ICLR poster\", or asks to design/edit a research poster."
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, AskUserQuestion, WebFetch, WebSearch
---

# posterly — HTML/CSS Academic Poster Workflow

A poster is **one HTML file** styled for an exact print canvas, rendered to PDF via Playwright + Chromium. Iterate by **measuring**, not eyeballing — the screen preview lies; only `emulate_media("print")` at the correct viewport tells the truth.

## Mental model

```
   HTML (with @page { size: W H })
     │
     ▼  print-emulate Chromium at W×96 × H×96 px viewport
     │
     ▼  data-measure-role tags identify columns/hero/footer-strip
     │
     ├──→ tools/poster_check.py measure  (HARD GATE — spread < 5 px,
     │                                    gap-to-strip ∈ [30,50] px,
     │                                    intercard gap ∈ [12,50] px,
     │                                    poster bbox aligns to page
     │                                    within ±2 px)
     ├──→ tools/poster_check.py preflight  (LaTeX residue, math `<`, missing imgs)
     ├──→ tools/render_preview.py  (PDF + thumbnail)
     └──→ tools/poster_check.py verify-final  (PDF page count / dims / size)
```

The skill is venue- and lab-neutral by default. Pick a template from `templates/README.md`, edit `:root` design tokens for your colors, fill TODO placeholders with your paper's content.

## Canvas constants

| Constant | Value | Notes |
|---|---|---|
| `--u` (CSS unit) | print = `1mm`, screen = `1.6px` | Use `calc(N * var(--u))` for ALL sizing. |
| Print viewport (px) | `W_in × 96` × `H_in × 96` | Computed by `poster_check`/`render_preview`. |
| Body cols | 2 / 3 / 4, or 1 hero + 1 column | Per template. |
| Strict alignment | **spread < 5 px** (aim < 3) | Hard, non-negotiable gate. |

## Workflow

### Step 0 — Pull the venue's official poster guidelines

Conference specs change year-to-year and vary wildly between venues:

- ICML often goes 60×36 in landscape; **ICLR has been 24×36 in portrait** in recent years; **NeurIPS** historically allowed multiple sizes; **CVPR** has used A0 portrait. Don't assume.
- Font minimums (≥24pt body for some venues), bleed margins, allowed orientations, on-poster logos, anonymity rules, QR-code policies — all vary.

Procedure:
1. `WebSearch` for `"<venue> <year> poster instructions"` or `"<venue> <year> poster size"`.
2. `WebFetch` the venue's official page; extract **dimensions, orientation, font-size floor, logo policy, anonymity rules, file-format requirement, template link if any**.
3. If paywalled or down, check OpenReview's call-for-papers or ask the user for the relevant section.
4. Echo the extracted spec back to the user in one short table **BEFORE** drafting. Confirm before proceeding — a wrong canvas size invalidates every alignment decision downstream.

### Step 0.5 — Design discovery (one round of AskUserQuestion)

Don't pick a template, colors, logos, or a QR target silently. Ask the user, in one batch (≤ 4 questions — the AskUserQuestion cap):

- **Layout**: "Which gallery template fits best? (a) 4-column landscape, (b) hero + supporting column landscape, (c) 2-column portrait." Show them `templates/README.md`'s table.
- **Palette**: "Lab/venue colors? E.g. `#XXX` accent + `#YYY` highlight. Default = neutral slate-blue + gold."
- **Logos & venue mark**: "Any logos to place? Affiliation / lab logo, and the conference / journal logo — give paths or URLs, or say 'none'." Don't assume a venue logo is wanted; cross-check the logo policy from Step 0 (some venues forbid them). When logo files are provided, inspect each one (aspect ratio, transparency, background — Step 2 item 5) and pick a size class + chip treatment per **Gate E — Header logos** below; don't just drop them in at the default size.
- **QR code**: "Want a QR code? If so, pointing at which link — paper / arXiv / code repo / project page — or none?" Generate it **offline** as a local image (see Customizing in README / `qrencode`); never leave a remote QR-service URL in the poster — it hangs `measure`'s networkidle wait and link-rots in print/archive.

Persist the user's answers as you go — re-reading them later prevents "improvement" loops that revert deliberate decisions.

### Step 1 — Confirm content & figures

Once layout is picked, ask once:
- **Source paper** path (`paper-overleaf/.../main.tex` ideal). Read the abstract, intro, headline results. Don't draft from memory — pull actual numbers, dataset names, equations.
- **Figures**: match `images/` filenames to paper figures.
- **Corresponding-author marker**: which author gets `✉`? Any starred (`★`) co-authors?
- **Items to preserve/exclude**: which sections to drop, any "do not revert" notes.

### Step 1.5 — Content audit (strongly recommended)

Before laying out, the draft must be audited for paper-to-poster fidelity. Past sessions caught real bugs ONLY here — paper said "20× fewer" but the table gave 16×, "fewest trajectories" was an overclaim vs the actual baselines, theorem preconditions were silently dropped. Skip this and you will discover errors only when standing next to the printed poster.

**How to run it (in order of preference):**

1. **External LLM reviewer with file access (best).** If you have Codex MCP, GPT-5 with file access, another Claude session, or any reviewer that can `Read` paper source files, use that. Recommended defaults if you have Codex MCP: `model="gpt-5.5"`, `model_reasoning_effort="xhigh"`, `sandbox="danger-full-access"` (read-only audit). Send the evidence pack + reviewer prompt below.

2. **Self-audit (fallback).** Walk every numeric claim on the poster and find its `file:line` in the paper source. Build the claim → evidence table by hand. Slower, easier to miss things, but better than skipping.

**Evidence pack the reviewer needs:**
1. The current `poster.html` (full)
2. Paper source path(s) so the reviewer can `Read` the `.tex` and any `results/` CSVs
3. For every numeric claim, the paper `file:line` where the number originates
4. For every theorem/claim, the paper statement verbatim with all preconditions

**Reviewer prompt template** (use this verbatim, fill bracketed parts):

```
Audit the academic-poster draft at [poster.html abs path] against the paper at [main.tex abs path] (and any results in [results dir]). For every number, claim, theorem, dataset name, and method-comparison on the poster, produce a claim → evidence table:

  | claim on poster | paper file:line | paper says (verbatim) | match? |

Mark "match?" as: OK / NUMERIC-MISMATCH / OVERCLAIM / MISSING-PRECONDITION / NOT-IN-PAPER / SCOPE-NARROWED.

Then list every NON-OK row as a problem to fix before printing. Be skeptical — "all <method> methods" claims, "best by Nx" claims, and theorem statements without their epsilon/regularity preconditions are the most common silent errors.
```

You may proceed to Step 2 **only after every finding is either fixed or explicitly recorded as "user-acknowledged tradeoff"**. Do not silently defer.

### Step 2 — Image preprocessing (optional but reduces re-renders)

For each paper figure you'll use:

1. **Vector source (EPS / PDF figure)?** Chromium `<img>` renders **neither EPS nor PDF** (converting to PDF does not help — also not embeddable), so a vector figure must be converted first. **SVG** is best — it stays crisp at poster scale. If a vector converter is already installed (`inkscape`, `pdf2svg`, `dvisvgm`), go straight to SVG. If none is installed, **ask the user** (one AskUserQuestion) whether to install one for a sharp vector figure, or rasterize to PNG instead — don't decide silently:
   - **Willing to install → SVG** (preferred): e.g. `inkscape fig.eps --export-type=svg`, or `pdf2svg fig.pdf fig.svg`.
   - **Decline → high-res PNG**: rasterize with Ghostscript at ≥ 2× rendered px — `gs -dSAFER -dBATCH -dNOPAUSE -dEPSCrop -r600 -sDEVICE=png16m -o fig.png fig.eps` (PIL works too; it shells out to `gs`: `Image.open('fig.eps').load(scale=5)`).

   Never embed the `.eps` / `.pdf` directly — it renders blank, caught only late as `polish`'s FIG/BROKEN after a wasted render.
2. **Autocrop whitespace** with PIL.ImageChops so the figure fills its card.
3. **Re-export at ≥ 2× the rendered px**. A `200u × 120u` figure print-rendered at 96 ppi → ~756 × 454 px. Source PNGs must be ≥ 1500 × 900 to look crisp at print.
4. **QR codes**: request at ≥ 2× rendered px (e.g., 480×480 if displayed at ~240 px).
5. **Logos**: inspect each user-provided logo file before placing it, then pick a size class and chip treatment from the two tables in **Gate E — Header logos** below. Use the same `python` that runs the posterly tools; this snippet needs Pillow (`pip install Pillow` if missing):

   ```python
   from PIL import Image
   src = Image.open("images/lab-logo.png")
   w, h = src.size
   has_alpha = src.mode in ("RGBA", "LA", "PA") or "transparency" in src.info
   im = src.convert("RGBA")
   im.thumbnail((512, 512))  # analysis-only downscale
   tw, th = im.size
   px = im.load()
   edge = ([px[x, 0] for x in range(tw)] + [px[x, th - 1] for x in range(tw)]
           + [px[0, y] for y in range(th)] + [px[tw - 1, y] for y in range(th)])
   white_edge = sum(a > 240 and min(r, g, b) > 245
                    for r, g, b, a in edge) / len(edge)
   lum = sorted(0.2126 * r + 0.7152 * g + 0.0722 * b
                for r, g, b, a in im.getdata() if a > 32)
   p10, p90 = (lum[len(lum) // 10], lum[(len(lum) * 9) // 10]) if lum else (0, 0)
   print(f"AR={w / h:.2f}  alpha={has_alpha}  white_edge={white_edge:.0%}  "
         f"mark lum p10/p90={p10:.0f}/{p90:.0f}")
   ```

   Reading the output: `AR` drives the size class (Gate E table 1). `white_edge >= ~70%` on an image **without** alpha means a bare white background (Gate E table 2's "stray white rectangle" case). The mark's luminance **percentiles** — not the mean — say whether the marks are dark (`p90 < ~120`) or light (`p10 > ~200`); a white-filled logo with a thin dark outline fools a mean. An **SVG** logo can't be opened by PIL — parse its `viewBox` for the AR and judge the chip from the rendered header crop in Step 5 instead.

### Step 3 — Scaffold from the gallery

1. `cp templates/<chosen>.html <work-dir>/poster.html`.
2. Edit the `:root` design tokens (single block; affects everything).
3. Replace `<title>`, header (title/subtitle/authors/affiliation), banner (if any), column cards, takeaways strip (if any), footer.
4. Match the template's `data-measure-role` scheme — DO NOT remove these attributes. The measurement script depends on them.
5. **No logo / QR provided:** keep the venue as its **text** badge — don't fabricate a venue logo. With no affiliation logo, **delete the empty `.logo-slot`** rather than leave a hollow box; the text affiliation line and the corner `.ornament` carry attribution. With no QR, delete `.qr-block`. Never fetch or invent an asset the user didn't give, and never leave a remote QR-service URL in the poster (offline local image only).

A gallery template is a **scaffold**: it passes `preflight` (structure) as shipped, but with figures commented out and copy as `TODO` stubs it is **expected to fail `measure`/`polish`** (columns only fill the top, so the column-bottom spread and gap-to-footer are far out of band). Those two gates judge a *filled* poster — they go green only after Steps 4–6 below, once you've added real content and balanced the columns. Don't try to "fix" a fresh scaffold to pass `measure`; fill it first.

Tools live in `tools/` and read `@page` from the HTML, so they're canvas-agnostic — the same commands work for ICLR portrait and ICML landscape.

### Step 4 — Render + measure loop (HARD GATE)

```bash
# After every layout change:
python <skill>/tools/poster_check.py measure poster.html
```

Targets (defaults; configurable via flags):
- **`spread < 5 px`** across the last-card-bottoms of all columns (+ any hero panel). Aim `< 3 px`.
- **`gap to footer-strip/footer ∈ [30, 50] px`** — card shadow visible but cards don't float.
- **`intercard gap ∈ [12, 50] px`** — whitespace between consecutive stacked cards inside a column (side-by-side cards count as one row). The ceiling catches `justify-content: space-between` faking bottom alignment on an under-filled column: spread reads ~0 and the footer gap lands in band while a void sits mid-column (observed in the wild: 98–135 px voids against a 22.7 px design row-gap). The floor catches cards packed so tight the drop shadow (`0 2u 6u` in shipped templates) is buried under the next card, fusing the stack into one slab. Tune via `--max-intercard-gap` / `--min-intercard-gap` (floor 0 to disable for shadowless themes).
- **`position align ≤ 2 px`** (authoritative) — the `[data-measure-role="poster"]` bounding box must sit at `(0, 0)` to `(viewport_w, viewport_h)` within `--position-tol-px`. This IS the full-canvas requirement: a poster whose bbox aligns to the page is necessarily full-bleed. Catches `transform: translate*`, mis-positioned `position: absolute`, stray body margin in print, and CSS source-order cascade bugs where a screen rule wins over a print override.
- **`canvas-fill ∈ [95 %, 101 %]`** (coarse early diagnostic) — `[data-measure-role="poster"]` width/height ratio against the print viewport. Fires before the position check when the ratio is FAR off, with a more diagnostic error message that points at the common `@media print { :root { --u: 1mm } }` omission (renders at ~42 %) or hardcoded `width > @page` (renders at >100 %). For borderline 95–99 % cases, position-align is the truth. Tune via `--min-canvas-fill` / `--max-canvas-fill`. **Safe-area design** belongs as internal padding on a full-bleed `.poster`, NOT as a smaller poster — a smaller poster fails position-align.

**This gate is non-negotiable.** If `measure` exits non-zero, fix the layout — do NOT continue to render. Common fixes:
- spread > 5: shrink the column with the lowest last-card by reducing a paragraph's `margin-bottom` by 1u, trimming one line, or shrinking a fixed-height figure by 5u.
- intercard gap > 50: an under-filled column is being stretched. Remove `justify-content: space-between`/`space-around` from the column, use a fixed `gap`, and absorb the slack with CONTENT (grow a figure, add paper-sourced text per Gate C) — never with whitespace.
- intercard gap < 12: an over-full column is being squeezed by shrinking the row-gap, which buries card shadows. Restore the design `gap` (6u ≈ 22.7 px) and take the height back out of content instead (trim a paragraph, shrink a figure by 5u, or move a card to a shorter column).
- gap > 50 everywhere: body-grid is too tall; grow a card or accept whitespace.
- gap < 30 anywhere: banner/header outgrew its slot; check `.framework-banner` rendered height.
- position misaligned (the usual full-canvas failure): make `.poster` full-bleed (`width: 100%; height: 100%; margin: 0; padding: 0` in `@media print`); remove any `transform: translate*` or `position: absolute` offsets; ensure `html, body { margin: 0; padding: 0 }` in the print media query; and check that the print `@media` block comes AFTER the screen `.poster` rule so source-order cascade resolves the print override winning.
- canvas-fill < 95 % (diagnostic fired first): poster forgot `@media print { :root { --u: 1mm } }` so it renders at screen scale. Add the override.
- canvas-fill > 101 % (diagnostic fired first): hardcoded `width: 1600px` (or similar non-`--u`-based size) exceeds `@page`. Replace with `calc(N * var(--u))`.

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

Run preflight in parallel:

```bash
python <skill>/tools/poster_check.py preflight poster.html
```

Catches: LaTeX residue (`\ref{`, `\cite{`, `\textbf{`, lone `\ `), bare `<` inside `$…$` math (MathJax mis-parses as HTML tag), missing local images, missing `data-measure-role="poster"`, unknown role values.

### Step 5 — Render + visual inspection

```bash
python <skill>/tools/render_preview.py poster.html
pdftoppm -r 100 poster_preview.pdf poster_check -png -f 1 -l 1
# then Read the resulting PNG
```

For dense regions, crop with PIL and read the slice — full poster at r=100 is ~6000 px wide; useful regions (header, banner, takeaways, one column) at full res reveal text wrapping issues invisible in the thumbnail.

### Step 6 — Polish

After alignment is solid, run the **visual polish gate**:

```bash
python <skill>/tools/poster_check.py polish poster.html
```

This is a **soft** gate (exits 0 by default; pass `--strict` to fail on warnings). It surfaces failure modes that the hard alignment gate cannot see — figure sizing relative to its aspect ratio, typography orphans, column whitespace pretending to be balance, `<br>`-in-flex collapse, and header-logo problems (broken / oversized / QR-height mismatch / title squeeze). See **§Visual polish gates** below for the rule for each WARN class and the correct fix. Fix every WARN unless you explicitly judge it acceptable for this poster.

Other polish:
- **`text-wrap: balance`** on banner/takeaways prose — fixes ragged-right and single-word-orphan lines.

**Step 6.5 — Final review (strongly recommended)**: send the rendered PDF (or its high-res PNG slices) AND the HTML to the same kind of reviewer used in Step 1.5 (external LLM if available, self-audit otherwise). Same evidence-pack rule. The reviewer prompt focuses on three things distinct from Step 1.5:
1. **Visual rhetoric**: does the poster's narrative carry? Are the headline numbers prominent? Is the framework banner readable from 2 m?
2. **Residue**: any `\ref{`, `\cite{`, leftover `TODO`, raw `<` in math, missing image, broken QR link.
3. **Final claim audit**: re-check numbers and overclaims AFTER content has been polished — polish often introduces new claims ("a key advantage of…") that were not in the original draft.

Fix every finding before declaring the poster done.

### Step 7 — Final verification

```bash
python <skill>/tools/poster_check.py verify-final poster_preview.pdf \
    --canvas 60x36in --max-size-mb 20
# or read the expected canvas from the companion HTML:
python <skill>/tools/poster_check.py verify-final poster_preview.pdf \
    --from-html poster.html
```

Checks: page count == 1, dimensions match canvas, file size ≤ limit. `--canvas` accepts inch dimensions (`60x36in`) or named sizes (`A0 portrait`, `A1 landscape`). By default rejects swapped W/H unless the PDF declares `Page rot ∈ {90, 270}` or you pass `--allow-rotated`. `--from-html <path>` reads `@page { size: … }` from the HTML so they can't drift apart.

Then report to the user:
- File path of PDF
- Final spread (px) and gap-to-footer range
- Any unresolved Codex feedback
- Page-fit confirmation

## Visual polish gates (Step 6 — soft gate)

Alignment passes but the poster can still look amateur. These three failure modes recurred across sessions enough to be promoted to first-class checks. `tools/poster_check.py polish` surfaces each as a WARN; the rules below explain how to fix.

### Gate A — Figure sizing by aspect ratio

A figure too small for its column is more wasteful than one too big. Pick width by the figure's intrinsic aspect ratio (`AR = naturalWidth / naturalHeight`), NOT by a fixed default:

| AR range | Shape | Aim for | `polish` warns below / above |
|---|---|---|---|
| `AR > 1.3` | Wide (workflow diagram, comparison chart) | **70–100%** of card width | < **65%** ⇒ FIG/WIDE. Avoid image-left/text-right in a narrow column — text gets squeezed to nothing (deliberate, balanced exception: the `data-fig-layout="beside-text"` opt-out below). |
| `0.8 ≤ AR ≤ 1.3` | Square-ish (block diagram, scatter) | **55–75%** of card width | < **55%** ⇒ FIG/SQUARE. |
| `AR < 0.8` | Tall (multi-series bar, long pipeline) | **45–60%** (centered if text-sparse, **wrapped** if text-rich) | < **36%** centered ⇒ FIG/TALL-SMALL (small + side voids); > **70%** ⇒ FIG/TALL. |

Thresholds are tunable via `--wide-min-ratio` / `--square-min-ratio` / `--tall-max-ratio` / `--tall-min-ratio`. The defaults bracket the documented "aim for" range, so a figure inside it passes cleanly. `--tall-min-ratio` (default **0.36**) is a *hard floor, not the ideal* — a centered tall figure rendering below it (≈ a 64%+ symmetric side void) is the recurring "figure too small" bug; the ideal is still 45–60%. The floor is measured as **rendered width ÷ card width**, which runs a few points below the CSS `width:%` (card padding), so calibrate against the rendered figure, not the style value. Because `polish` is soft, a borderline figure you've consciously accepted can keep its WARN; raise the floor and run `--strict` if you want it enforced.

A figure whose `<img>` fails to load (missing file, 404, or unreachable remote URL) reports zero natural size and warns as **FIG/BROKEN** — it will be blank in print. An SVG legitimately reports zero intrinsic size, so it's exempt from FIG/BROKEN — but the AR sizing gates **still apply to it**, computed from its **rendered** aspect ratio (so a too-small/too-wide SVG figure is not silently exempt). The probe covers both card and hero-panel `<img>` (the hero centerpiece is the worst image to silently lose); the AR sizing gates stay card-only. One known gap: an SVG served from an extensionless URL still slips the FIG/BROKEN exemption heuristic (gets wrongly flagged broken).

Concrete bad case (prior session): `co-consideration.png` (AR ≈ 1.41) shipped at 41 % column width. The whitespace beside it conveyed nothing and the figure was unreadable from 2 m. Fix: 66 % width, no text-right.

**Deliberate image-left/text-right (the opt-out).** FIG/WIDE fires on a wide figure sized below 65 % because the *usual* cause is the bad case above — a figure shrunk into a gray margin. But a wide figure that **shares its card with a meaningful text column** (figure left, explanatory annotations right) is a legitimate layout when the text genuinely earns its space and isn't squeezed to a sliver. For that case, mark the `<img>` with `data-fig-layout="beside-text"`:

```html
<img src="images/dynamics.png" alt="Training dynamics"
     data-fig-layout="beside-text" style="width: 100%">
```

This skips the AR width gates (FIG/WIDE / FIG/SQUARE / FIG/TALL / FIG/TALL-SMALL) for that image only — **FIG/BROKEN still applies** (a blank image is a bug regardless of intent). The attribute records the design decision *in the markup*, so a later edit (human or agent) reads "this figure is intentionally beside text" and leaves the layout alone instead of widening it to silence the warning. Use it only after you've eyeballed the render and confirmed the text column isn't squeezed — it is an opt-out for a *verified-good* layout, not a way to mute a real warning. `examples/powerflow_icml2026/poster.html` uses it on its training-dynamics card.

**Center vs. wrap a tall figure (AR < 0.8).** A tall figure is *too small* just as easily as too wide — shrunk to ~35 % and centered it's illegible with a big symmetric side void on each margin (the recurring bug `FIG/TALL-SMALL` now catches below a 36 % rendered width). Which layout to use is driven by **how much text shares the card**:

- **Text-rich card → wrap** the figure: text flows *beside and below* it, so the image can be large. Float it with `.fig-wrap` / `.ff-fig` (shipped in every template) and mark the `<img>` `data-fig-layout="beside-text"`. The figure **and** its surrounding text must live inside one `.fig-wrap` — the clearfix is what makes the card grow to contain the float; a bare floated `<img>` escapes the card box and `measure` then reads the wrong card bottom.

  ```html
  <div class="card" data-measure-role="card">
    <div class="section-title">…</div>
    <div class="fig-wrap">
      <figure class="ff-fig" style="width: 49%">
        <img src="images/arch.png" data-fig-layout="beside-text">
        <figcaption class="caption">…</figcaption>
      </figure>
      <p>…body text wraps to the left of, and then below, the figure…</p>
      <ul>…</ul>
    </div>
  </div>
  ```

- **Text-sparse card → center** the figure (`.figure`) at 45–60 %. There isn't enough text to wrap, so a float just leaves an L-shaped void; a centered figure at a healthy width reads cleaner. (Worked example, same poster: the architecture figure was *wrapped* — lots of surrounding text — while the Multi-Head figure was *centered* — sparse text. Opposite calls, driven by text volume, not by the figure.)

`data-fig-layout="beside-text"` is the opt-out marker for **either** layout (flex side-by-side *or* float-wrap) — it records "this figure intentionally shares its card with text" and skips the AR gates. It is **not** a generic mute: don't tag a centered, text-less small figure with it. Either enlarge it, wrap it, or (since `polish` is soft) accept the `FIG/TALL-SMALL` WARN.

### Gate B — Typography orphans

`measure` checks card bottoms; it does NOT see a `↑` or superscript that wrapped alone onto its own line — a small but jarring artifact 2 m away.

Known orphan-prone patterns:
- Stat numbers with trailing arrows: `1.18–1.30× ↑`, `18.24% ↓`
- Number + unit / multiplier: `4096 × 4096`, `7 nm`, `2248×`
- Trailing footnote markers: `BraVE*`, `MEAN§`

Defenses (preferred → fallback):

1. **`white-space: nowrap`** on the smallest element whose innerText must stay one line (`.stat-num`, `.hs-stat .num`, `.takeaway-num`). Blanket — text simply does not break.
2. **Non-breaking glue** between the last two tokens: `1.18–1.30×&nbsp;↑`. Use when nowrap would overflow a tight card.
3. **Reword to put the marker first**: `↑ 1.18–1.30× speedup` — arrow becomes the line's first token, can't orphan.

`polish` flags an element (`[class*="stat"], [class*="num"], .takeaway-num, .hs-stat, .headline-num`) only when its text **ends with a whitespace-separated trailing glyph** from `↑↓↔×÷±§¶†‡*°%` and lacks `white-space: nowrap` — i.e. a lone glyph token that could wrap by itself, like `1.18–1.30× ↑` or `18.24% ↓`. It does **not** catch fused forms such as `4096 × 4096`, `7 nm`, `2248×`, `BraVE*`, or `MEAN§` (the text doesn't end on a space-separated glyph) — guard those by hand with the defenses above.

### Gate C — Content-driven balance, not space-between-driven

`justify-content: space-between` on a column is a shortcut to bottom-align last cards across columns. It works ONLY when the cards' natural heights are within ~5% of each other. When they aren't, space-between fills the delta with empty pixels — usually one giant gap in the column with the smallest content.

**Symptom**: a column with one short card followed by 25 + mm of whitespace. Reads as "this column ran out of things to say".

**Wrong fix**: shrink `gap` globally to hide the whitespace. Peers still have meaningful internal gaps; reducing them makes the others claustrophobic.

**Right fix**: ADD MEANINGFUL CONTENT to the short column until it's within ~5 % of its peers' natural height. From the paper, recover:
- Sub-claims that were footnotes or implicit assumptions
- A 2–3 bullet "challenges" or "design choices" recap
- A short caption beside a previously-bare figure

Concrete bad case (prior session): the SnipSnap Motivation column shipped with a one-line "three challenges" summary, leaving a 13 mm space-between gap. Fix: expanded into 3 bullets matching the paper's challenge framing — column balanced via content, not whitespace.

Enforcement is two-layered. `measure` **hard-fails** any column whose gap between consecutive stacked cards exceeds `--max-intercard-gap` (default 50 px, absolute) — this is the backstop that catches the space-between shortcut regardless of mechanism (added after a production poster shipped 98–135 px voids with every gate green: spread read 0.00 px because space-between pinned the last card to the bottom, and the relative polish warn below stayed silent at 4–6 % of a 36-inch column). `polish` additionally warns earlier, when a column with computed `justify-content: space-between` has an inter-card gap exceeding 5 % of the column's height. Tune via `--max-space-between-fill`.

**The same trap, one card.** A single card set to `flex: 1` (the standard way to make its column reach the footer and satisfy `measure`'s spread/gap gates) is measured only by its **bottom edge** — a card stretched to twice its content's height passes `measure` with spread = 0 while the lower half is blank white. `measure` can't catch it (it checks only the bottom edge), so **`polish` does**: the **CARD/TRAILING** warning fires when a card leaves more than `--max-card-trailing` (default 10 %) of its height blank below its last line of content. A green bottom-edge gate is necessary, not sufficient. Never stretch a block to create whitespace just to make the layout "fit." Fix it the same way as Gate C, in order of preference: (1) fill the card with real content from the paper until it is comfortably full (aim ≥ ~80 %, not 46 %); (2) enlarge a fixed-height figure to carry the space with substance; (3) if the content genuinely is that sparse, choose a **smaller canvas** so it fills — a single paragraph does not belong on a 60-inch sheet. A half-empty card reads as "ran out of things to say" and is a failed poster even when every gate is green.

### Gate D — `<br>` line breaks inside a flex container

A `<br>` that is a **direct child of a `display: flex` / `inline-flex` element is blockified into a flex item and stops creating a line break** (CSS Flexbox spec — every in-flow child becomes a flex item). Intended multi-line content silently collapses: in `flex-direction: row` the "lines" lay out side-by-side on one row (often with a MathJax `<mjx-container>` baseline pulling one fragment up, so it reads as jagged "misaligned" text); even in `column` the `<br>` is a dead empty item. `measure` can't see it — the card bottom is unchanged — so it survives to print. Concrete bad case (prior session): an OPT-AIL banner loop label `↻<br>repeat<br>$K$ iters` rendered as `repeat` and `K iters` jammed onto one row instead of three stacked lines.

`polish` warns **LAYOUT/FLEX-BR** when any flex/inline-flex element has a direct `<br>` child, reporting the computed `flex-direction` so the fix is obvious. **Fix:** wrap each line in its own `<span>` (or `<div>`) and set `flex-direction: column` with `align-items: center` / `text-align: center`; or, if the element doesn't need to be flex, make it a plain block where `<br>` works normally. Never rely on `<br>` for layout inside a flex box.

### Gate E — Header logos (affiliation / venue) & title squeeze

Logos live in the header, outside any card or hero panel, so Gates A–D never see them. The failure modes are real and silent: a 404'd logo prints **blank**; a wide wordmark rendered at seal height becomes enormous and **squeezes the title** (the header grid is `auto 1fr auto` — an oversized right block steals width from the `1fr` title track instead of overflowing); a transparent dark mark **vanishes** on a dark header; a white-background JPG leaves a **stray white rectangle** on a colored one.

**Sizing.** The shipped `.logo-slot` uses a fixed height (so a low-res logo still upscales to target) plus a width cap with `object-fit: contain` as the extreme-AR safety net, and three size classes. Pick the class from the file's aspect ratio (the Step 2 logo inspection):

| Logo AR (w/h) | Shape | Class on `.logo-slot` |
|---|---|---|
| `< 0.7` | Tall stacked mark | `logo-tall` |
| `0.7 – 1.4` | Square seal / crest | `logo-square` |
| `1.4 – 2.5` | Mid wordmark | *(none — default)* |
| `≥ 2.5` | Wide wordmark (university name banner) | `logo-wide` |

`logo-wide` is **intentionally shorter than the QR** (≈ 68 % of its height) so a long wordmark doesn't out-mass it — that's why the QR-match gate below gives it a band instead of a strict match. The classes are starting defaults, not law: override per poster with inline `style="--logo-h: …; --logo-wmax: …"`, and let the rendered header crop (Step 5) be the final arbiter.

**Background (chip).** Decide from the Step 2 logo inspection + the header's own color:

| File analysis | Header zone | Treatment |
|---|---|---|
| transparent, dark marks (`p90 < ~120`) | dark / colored | wrap in `.logo-chip` (white) |
| transparent, light marks (`p10 > ~200`) | light | wrap in `.logo-chip.logo-chip-dark` |
| opaque, white edge majority | non-white | wrap in `.logo-chip` — the rounded padding absorbs the white box into a deliberate chip |
| transparent, contrast already fine | any | no chip |
| opaque white background | white / near-white | no chip needed |
| gradient / image header, or unsure | — | default to a chip (safer) |

```html
<!-- wide wordmark with a bare white background on a colored header -->
<div class="logo-slot logo-wide">
  <div class="logo-chip"><img src="images/univ-wordmark.png" alt="University"></div>
</div>
```

The chip wraps the `<img>` *inside* the `.logo-slot`, so the size class still bounds the image. Multiple logos: keep them in one `.right-block` and give them the **same** size class so the strip reads level. **Portrait posters: never place a wide wordmark and the QR side by side** — the narrow header can't afford both (HEADER/TITLE-SQUEEZED will fire, by design); stack them or drop one. A custom **venue logo** (inside `.venue-badge`) gets the same chip workflow and the broken-image check, but not the QR height match — it sits left of the title at its own scale.

**What `polish` checks** (all soft WARNs; venue badge: first two only):

- **LOGO/BROKEN** — a non-SVG header logo with zero natural size failed to load and will be blank in print (the FIG/BROKEN blind spot this gate closes).
- **LOGO/WIDE** — a logo wider than `--logo-max-width-ratio` (default **22 %**) of the header width crowds the title. Fix: set the right size class (`logo-wide` caps a wordmark), not a hand-tuned pixel width.
- **LOGO/QR-MISMATCH** — a non-wide logo whose height differs from the QR's by more than `--logo-qr-tol` (default **15 %**), or a `logo-wide` slot outside the **55–85 %** band of QR height. The header strip should read level. Skipped when there's no QR.
- **HEADER/TITLE-SQUEEZED** — the aggregate signal: the right block (`.right-block` / `.right-stack`) exceeds `--rightblock-max-ratio` (default **32 %**) of header width, or the title block drops below `--title-min-ratio` (default **45 %**). Individual logos can each pass while their sum still crowds the title — this catches the sum. Fix: shrink/stack the side blocks or drop an asset.

The defaults are calibrated against the size classes, so a logo sized by the recommended class never trips its own gate. Gate E only sees logos inside the **header** (`data-measure-role="header"`) under the `.logo-slot` / `.venue-badge` class names — when restyling, keep those classes on the wrappers (a hand-rolled `.aff-logo` class makes the logo invisible to the gate). **Bare-white detection is workflow-only, not a gate** — whether a logo "sits on a non-white background" isn't robustly decidable from static analysis, so apply the chip per the table above and verify on the rendered crop; don't expect `polish` to catch a missed chip.

## Universal pitfalls (apply to all templates)

1. **`<` raw in MathJax inline** → may be HTML-parsed before MathJax sees it (mode-dependent). Prefer `\lt` everywhere. Preflight catches `(?<!\\)<(?![=/!])` inside `$…$` / `$$…$$` / `\(…\)` / `\[…\]` — i.e. raw `<` NOT preceded by a backslash and NOT followed by `=` / `/` / `!`. The `<=` case is intentionally exempt (single MathJax token, parsed atomically — no HTML-tokenizer ambiguity); preflight stays quiet about it, but `\le` reads more naturally in print.
2. **`\ ` (backslash-space) from LaTeX** → renders literally. Strip when porting from `.tex`. Preflight catches.
3. **Screen-mode measurement is misleading.** Always use `tools/poster_check.py measure` — never eyeball the screen render.
4. **Pre-compact `\\ ` and lone `<`** — preflight catches before render.
5. **`text-wrap: balance` needs Chromium ≥ 114** — Playwright's bundled Chromium is fine.

## Layout-shared pitfalls (column-based templates)

6. **`overflow: hidden` on `.body-grid` clips card shadows.** If last card sits at body-grid bottom, its 30-px shadow is cut and visually merges into the strip below.
7. **`padding-bottom` on `.column` does NOT push cards down** (cards stack from the top in flex; column padding only reserves space below). But `padding-bottom` on the **last card** *does* raise that column's bottom — `measure` reads the card's border-box bottom — so it's the one continuous, zero-reflow lever for a sub-line alignment residual (see Step 4 "fine-tuning levers"). Don't confuse the two; to shrink a column, edit card content directly.
8. **Title-block can dominate header height.** Shrinking logos/QR doesn't help if `.title-block` is already the tallest cell.
9. **Banner can grow from `.banner-stats`.** Big numbers cascade into body-grid shrinkage.
10. **`box-shadow: 0 2u 6u` extends ~30 px** below the card. Final last-card-bottom must be ≥ 30 px above the strip below.
11. **Image-left + text-right inside a narrow column wastes the image.** For wide images in narrow cols, keep image-on-top + caption-below.

## When to call an external LLM reviewer (three checkpoints)

The skill works fine without one, but a second pair of eyes reliably catches paper-to-poster fidelity bugs you'll otherwise discover next to the print station. Three natural checkpoints:

1. **Content critique** (Step 1.5) — does the poster's prose / numbers / claims match the paper?
2. **Theorem & equation pass** (after Step 3) — are theorem preconditions complete? Equations rendered correctly?
3. **Final polish** (Step 6.5) — fresh eyes on the assembled poster for residue and overclaims.

The bias is **send when uncertain**. Cost: 2-3 min. Cost of a silent error in a poster you'll print and stand next to for 2 hours: high.

**Recommended reviewer settings (if you have Codex MCP):** `model="gpt-5.5"`, `model_reasoning_effort="xhigh"`, `sandbox="danger-full-access"` (read-only review; the sandbox often fails to start in containers / nested namespaces and the audit is read-only anyway). Any other capable reviewer LLM that can `Read` paper files works equally well — see Step 1.5 for the canonical prompt template.

## Tools

```
tools/
├── poster_check.py   ← CLI: measure / preflight / polish / verify-final
├── render_preview.py ← CLI: print-emulated PDF + thumbnail PNG
└── _posterly/        ← internal modules (canvas parser, Playwright + settle, etc.)
```

- `poster_check.py`:
  - `measure` — **hard** alignment gate (column-bottom spread < 5 px, gap-to-footer in [30, 50] px, intercard gap in [12, 50] px inside each column, canvas-fill ∈ [95 %, 101 %] as a coarse diagnostic, and poster bbox aligns to the page within ±2 px — the bbox-alignment check is the authoritative full-canvas requirement).
  - `preflight` — static HTML lint (LaTeX residue, math `<`, missing images, role validation).
  - `polish` — **soft** visual gate (figure sizing by AR, broken images, typography orphans, space-between fill, `<br>`-in-flex collapse, header logos: broken / oversized / QR mismatch / title squeeze). Warns by default; `--strict` to fail. Hard-fails if the poster has no `[data-measure-role]` markup at all (silent PASS would be a worse bug).
  - `verify-final` — `pdfinfo`-based PDF sanity (page count, dimensions, file size).
- `render_preview.py` — Playwright print-emulated PDF + scaled PNG thumbnail.

All scripts read `@page { size: W H }` from the input HTML so the same code handles ICML 60×36 landscape, ICLR 24×36 portrait, CVPR A0, etc. without flags.

## Templates

See `templates/README.md` for the gallery. Current set:
- `landscape_4col_neutral.html` (60×36 in, 4 cols)
- `landscape_hero_neutral.html` (60×36 in, hero + supporting col)
- `portrait_2col_neutral.html` (24×36 in, 2 cols)

Adding a template: keep it neutral (no lab branding), preserve `data-measure-role` scheme, document the row in `templates/README.md`.

## Key rules

- **Never invent paper numbers.** Read the `.tex` source. Bench numbers, datasets, model names — all verifiable.
- **Card-shadow visibility is non-negotiable.** A poster looks cheap when shadows are clipped.
- **Strict alignment is non-negotiable.** Spread < 5 px or it's not done — do not report success until `measure` exits 0.
- **Preserve user-judgment decisions across sessions.** "Do not revert" notes (`✉ stays on Author X`, `α-sensitivity card removed`) — re-read the user's prior messages before "improving" a section.
