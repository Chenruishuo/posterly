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

Don't pick a template, colors, logos, a QR target, or the text density silently. Ask the user in one round. AskUserQuestion takes at most 4 questions per call, so if more than four of the topics below need input for this poster, send the four most decision-relevant first and ask the rest (usually QR) in a brief second call:

- **Layout**: "Which gallery template fits best? (a) 4-column landscape, (b) hero + supporting column landscape, (c) 2-column portrait." Show them `templates/README.md`'s table.
- **Palette**: "Lab/venue colors? E.g. `#XXX` accent + `#YYY` highlight — or say 'you pick'." When the user gives colors, use them. When they don't, do **not** silently fall back to the one house style: derive a poster-specific palette from the materials at hand (**§Palette derivation** below) and propose it in this same round — "suggest `#660874` from the Tsinghua brand — OK?" — so the user can veto cheaply. The neutral slate-blue + gold shipped in the templates is the *last-resort* fallback, not the default.
- **Logos & venue mark**: "Any logos to place? Affiliation / lab logo, and the conference / journal logo — give paths or URLs, or say 'none'." Don't assume a venue logo is wanted; cross-check the logo policy from Step 0 (some venues forbid them). When logo files are provided, inspect each one (aspect ratio, transparency, background — Step 2 item 5) and pick a size class + chip treatment per **Gate E — Header logos** below; don't just drop them in at the default size.
- **QR code**: "Want a QR code? If so, pointing at which link — paper / arXiv / code repo / project page — or none?" Generate it **offline** as a local image (see Customizing in README / `qrencode`); never leave a remote QR-service URL in the poster — it hangs `measure`'s networkidle wait and link-rots in print/archive.
- **Text density**: "How much text should the poster carry? (a) **Normal** (default) — posterly's usual concise balance of prose and paper figures; (b) **Light** — fewer words, with the saved space reassigned to paper-sourced figures/diagrams across the poster." For **Light**: trim secondary prose and merge or drop low-value text cards *only* when the freed area becomes visual real estate — larger AR-appropriate figures, figure-dominant cards, or additional useful paper visuals. Keep multiple figures while each stays legible; do **not** concentrate the budget into one enlarged centerpiece or switch layouts for that reason. "More room" means larger, clearer visual regions — never blank columns / cards / gaps: `measure`, Gate A, Gate C, `CARD/TRAILING`, `FIG/BESIDE-TEXT-VOID`, and `HERO/STAGE-LETTERBOX` all still apply.

Persist the user's answers as you go — re-reading them later prevents "improvement" loops that revert deliberate decisions.

### Palette derivation (when the user has no color preference)

A paper already carries brand signals — the default palette should be **derived from them, not house-styled**. Pick the seed color from whichever signal is strongest for *this* poster (judgment call, no fixed priority):

- **Affiliation brand color** — the official identity color of the dominant lab/university (your own knowledge or a quick web check: Tsinghua purple, MIT cardinal, ETH blue…). Strongest choice when one affiliation dominates the author list.
- **A provided logo** — extract its dominant saturated color (snippet below).
- **Venue identity** — if the conference has a recognizable brand color.
- **The paper's own figures** — dominant hue of the headline figure; the poster then echoes its figures.
- **Field/topic conventions** — weakest signal; use only when nothing above gives a usable color.

Whatever the source, the seed feeds one fixed recipe — the rebrand surface is the same six tokens in every template (`--accent`, `--accent-deep`, `--accent-light`, `--accent-soft`, `--gold`, `--gold-soft`):

```python
from collections import Counter
from PIL import Image

def rel_lum(rgb):
    c = [v / 255 for v in rgb]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

def contrast(a, b):
    la, lb = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

def mix(rgb, other, t):  # t=0 -> rgb, t=1 -> other
    return tuple(round(v + (o - v) * t) for v, o in zip(rgb, other))

# 1) Seed. From an IMAGE (logo / headline figure): dominant saturated
#    mid-tone, bucketed so JPEG noise doesn't split the vote. From a BRAND
#    GUIDELINE: just set `seed` to the official hex and skip this block.
im = Image.open("images/lab-logo.png").convert("RGBA")
im.thumbnail((128, 128))
px = [(r, g, b) for r, g, b, a in im.getdata() if a > 128]
cands = Counter((r // 32, g // 32, b // 32) for r, g, b in px
                if max(r, g, b) - min(r, g, b) > 40       # saturated enough
                and 60 < (r + g + b) / 3 < 200)           # mid-tone
seed = (tuple(v * 32 + 16 for v in cands.most_common(1)[0][0])
        if cands else None)  # None = this image has no usable seed --
                             # try the next signal source, neutral only last

# 2) Tokens. Darken the seed until white text clears WCAG AA on it (the
#    same 4.5:1 also covers accent-as-text on white -- symmetric pair).
accent = seed
while contrast(accent, (255, 255, 255)) < 4.5:
    accent = mix(accent, (0, 0, 0), 0.08)
fmt = lambda c: "#%02X%02X%02X" % c
print(f"--accent: {fmt(accent)};  --accent-deep: {fmt(mix(accent, (0, 0, 0), 0.30))};")
print(f"--accent-light: {fmt(mix(accent, (255, 255, 255), 0.90))};  "
      f"--accent-soft: {fmt(mix(accent, (255, 255, 255), 0.82))};")
print(f"white-on-accent contrast: {contrast(accent, (255, 255, 255)):.1f}:1")
```

Rules that hold regardless of seed source:

- **Print-safe accent**: muted-to-medium saturation, medium-dark value. The AA loop above enforces the dark end; if a brand color is neon-bright, mute it toward the template's tone rather than shipping fluorescent ink.
- **Secondary (`--gold`) stays unless it clashes**: the warm gold works as "ours/best" emphasis against any *cool* accent. If the seed itself is warm (red/orange/yellow hue), swap the secondary to a deep cool neutral (e.g. `#3D4A5C`) so emphasis still pops; derive `--gold-soft` as its ~90% white tint.
- **Backgrounds stay near-white** (`--bg-page`/`--bg-card` untouched, or at most a faint seed-hued tint). Print legibility and every downstream check assume a light poster.
- **Echo the choice**: state the seed source and final tokens to the user (Step 0.5 round) and record them in your build notes — "accent #660874 from Tsinghua brand; gold kept" — so a later edit doesn't "correct" a deliberate derivation back to neutral.

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
6. **The takeaways strip is optional — decide, don't default.** The landscape scaffolds ship with a bottom takeaways strip, but it earns its place only as a genuine 60-second narrative exit (Idea / Method / Result / Practical). If the final column cards already land the conclusion, or it would just restate the body, **delete the whole `.takeaways-strip` block** rather than pad it — a redundant strip is worse than none (portrait templates omit it by design). Same spirit as *"Fill means substance"* below: don't add a block that doesn't carry its weight.
7. **The framework banner is optional too — same judgment, applied to the top.** A poster does not *have* to open with a `FRAMEWORK` / TL;DR strip. Keep the `.framework-banner` only when the paper genuinely compresses to one sentence plus 2–4 headline numbers worth reading from 2 m. If the contribution doesn't reduce to a single line, or the opening is better carried by a hero figure (`landscape_hero`) or by the first column itself, **delete the whole `.framework-banner` block** and let the body grid absorb the height (then rebalance through the Step 4 measure loop). A banner that merely paraphrases the title or pads generic stats is noise at the poster's most valuable position — worse than none.

A gallery template is a **scaffold**: it passes `preflight` (structure) as shipped, but with figures commented out and copy as `TODO` stubs it is **expected to fail `measure`/`polish`** (columns only fill the top, so the column-bottom spread and gap-to-footer are far out of band). Those two gates judge a *filled* poster — they go green only after Steps 4–6 below, once you've added real content and balanced the columns. Don't try to "fix" a fresh scaffold to pass `measure`; fill it first.

Tools live in `tools/` and read `@page` from the HTML, so they're canvas-agnostic — the same commands work for ICLR portrait and ICML landscape.

### Step 4 — Render + measure loop (HARD GATE)

> Or drive the whole loop with `run_gates.py` (see **§Enhanced gates & fix discipline**), which runs this `measure` gate plus `preflight` / `style` / `asset` / `polish` in one `GATE_REPORT.json`. The standalone `measure` call below is the minimum.

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
- **`text-wrap`** — match the property to the text:
  - **`balance`** only on **short, centered** display text (titles, captions, one-line takeaways ≤ 2 lines); it evens the ragged edge.
  - **Never `balance` on multi-sentence prose** (banner TL;DR, long takeaways), and especially not with `text-align: left`. Near a 2↔3-line threshold, balance shortens and hyphenates the **first** line to "even" the block, producing a crammed-left / big-gap-right banner. For prose that should fill its box, use **`text-wrap: pretty`** (fills each line, only protects the last-line orphan) or plain natural wrap.

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

A figure whose `<img>` fails to load (missing file, 404, or unreachable remote URL) reports zero natural size and warns as **FIG/BROKEN** — it will be blank in print. An SVG legitimately reports zero intrinsic size, so it's exempt from FIG/BROKEN — but the AR sizing gates **still apply to it**, computed from its **rendered** aspect ratio (so a too-small/too-wide SVG figure is not silently exempt). The probe covers both card and hero-panel `<img>` (the hero centerpiece is the worst image to silently lose). One known gap: an SVG served from an extensionless URL still slips the FIG/BROKEN exemption heuristic (gets wrongly flagged broken).

**Hero figures aren't exempt from sizing — HERO/STAGE-LETTERBOX.** The card-width AR gates above (FIG/WIDE etc.) don't apply to a hero panel, but a hero figure can still waste its space: a narrow-aspect picture dropped into a wide-but-**short** `.hero-stage` is height-constrained and strands itself with big symmetric side voids (a 2:1 panorama height-capped in a 5:1 stage fills ~35 % of the width). **HERO/STAGE-LETTERBOX** fires when the picture fills < 55 % of the stage width *while* the stage is much wider (relative to the image AR) than the image needs, with symmetric voids. The usual root cause is cramming a second large figure into the hero so the main figure loses vertical budget — move the secondary diagram into a card / the supporting column, or constrain the stage width toward the image's aspect ratio. A genuine full-bleed hero (image AR ≈ stage AR, picture fills the width) never trips it.

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
    <div class="section-title"><span class="num">N</span><span class="st-text">…</span></div>
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

That L-shaped void is now a measured WARN: **FIG/BESIDE-TEXT-VOID** fires when the wrapping text stops more than 30 % of the figure's height short of its bottom (text too short to fill the float). Fix it in this order: **(1) lengthen the text** with paper-sourced detail until it fills the figure height, or **(2) shrink the figure** to the text height. But don't manufacture filler the section doesn't need, and don't shrink a figure below 2 m legibility just to match a short text block: if the figure is the point and the prose would be padding, **convert the card to figure-dominant** — drop the float, size the figure by its aspect ratio (Gate A, i.e. *large*), give it a one-line caption, and let the presenter speak the detail (see "*Fill means substance*", Gate C). That is different from the trap below: a Gate-A-sized figure that owns the card vs. a small figure centered inside a still-text-shaped card. **Centering a beside-text float in place is the last resort, and only works for a WIDE figure (AR > ~1.3)** — centering a square or tall figure at a width that fits a column just swaps the L-void for *symmetric side voids* and shrinks the figure, which is a worse look, not a fix. (Worked example: a square 2×2 surface-plot figure (AR ≈ 1.0) with a one-line caption was first "fixed" by centering — it landed tiny with big blank margins on both sides; the real fix was to keep it beside-text and add two paper-sourced sentences so the prose filled the figure's height.)

`data-fig-layout="beside-text"` is the opt-out marker for **either** layout (flex side-by-side *or* float-wrap) — it records "this figure intentionally shares its card with text" and skips the AR width gates. It is **not** a generic mute: it does **not** skip FIG/BESIDE-TEXT-VOID (a beside-text float still has to be genuinely text-rich — tagging a short-text float won't silence the void), and don't tag a centered, text-less small figure with it. Either enlarge it, wrap it, or (since `polish` is soft) accept the `FIG/TALL-SMALL` WARN.

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

**Lone wrapped fragment — display text that breaks to a one-word last line.** The orphan logic extends from stat numbers to *any short display text that wraps* — a title, `.section-title`, banner headline, or one-line takeaway whose break strands a single short token alone on the final line. The worst case is when that lone token is a **word carrying a leading footnote/superscript marker** (a `*`- or `†`-prefixed term): stranded alone and left-aligned, the marker+word reads as a stray symbol or a typo, not a word. `polish` **does** catch this now (`WIDOW`): it measures wrap geometry on `.callout`, `.body-text`, `.caption`, `.section-title`, `.card p`, `.card li` — including each `<br>`-delimited segment — and warns when the last visual line holds exactly one word. Limits (still guard by hand): math/figures (`mjx-container`/`img`/`svg`/`table`) no longer hide a whole block — they join the line model as opaque cells, and only a last line that itself carries math/figure content is unjudgeable (a pure-text lone word after inline math IS caught); it still skips `white-space: nowrap/pre`, RTL, and running prose over ~220 chars (display text `.caption`/`.callout`: ~400); it counts an `&nbsp;`-glued multiword tail as multiple words (so glue *clears the `WIDOW` warning* — but see the gap caveat below), and a two-word last line is allowed. Fix a `WIDOW` (or a fused-glyph case the gate can't see) by the option that makes the lines **fill naturally**, not merely the one that silences the gate — in this order of preference: (1) **reword — expand or contract the sentence** — first choice for left-aligned prose (`.callout`, `.body-text`, `.caption`): move the break to a natural phrase boundary so the last line carries ≥2 words *and* the line above fills to the margin. Adding one word often does it (e.g. "expressive" → "highly expressive"). (2) **`text-wrap: balance`** on a *centered heading / title* evens the lines so no single word is stranded (the default on centered display text — keep it; never pair `balance` with `text-align: left`, per the wrap rules above). (3) **`&nbsp;` glue** is a **last resort**: it only moves the break point, so on left-aligned prose it trades the one-word orphan for a *ragged short line with a big right-side gap* — itself an artifact `polish` does **not** catch (it counts only last-line words, never how full the line above is). Glue is genuinely right only where a token *must not* open a line: a leading footnote/superscript marker (`…&nbsp;*term`) or a tight stat cell. After any fix, **re-render and look** — a cleared gate is necessary, not sufficient. Never ship a one-word last line, a lone `*` / `†` / `‡` fragment, or a line left half-empty by a glue "fix".

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

**"Fill" means substance, not word-count — and a figure is substance.** These anti-whitespace gates (Gate C, CARD/TRAILING, FIG/BESIDE-TEXT-VOID) exist to kill *empty pixels*, not to mandate dense prose. A poster is a **talk aid, not a self-contained paper**: you stand beside it, and the small details — a derivation step, a hyperparameter, an edge-case caveat — are yours to *say out loud*, not to cram onto the sheet. So the legitimate ways to fill a region are, in order: (1) a **larger, more legible figure** that earns the space; (2) **figure-only, or figure + a one-line caption**, when the figure already makes the point clearly — a self-explanatory plot does not need a paragraph restating it; (3) genuinely load-bearing prose. Reach for more text only when the *figure can't carry the point alone*. And figure legibility wins ties: if cramming text beside a figure would shrink it below what reads at 2 m, **drop the text and let the figure be big** (center it, short caption, presenter fills the rest) rather than starve the image to justify a paragraph. What these gates fail is a half-empty card or a thumbnail figure marooned in whitespace — **not** a clean card whose work is done by one big figure and a few words.

### Gate D — `<br>` line breaks inside a flex container

A `<br>` that is a **direct child of a `display: flex` / `inline-flex` element is blockified into a flex item and stops creating a line break** (CSS Flexbox spec — every in-flow child becomes a flex item). Intended multi-line content silently collapses: in `flex-direction: row` the "lines" lay out side-by-side on one row (often with a MathJax `<mjx-container>` baseline pulling one fragment up, so it reads as jagged "misaligned" text); even in `column` the `<br>` is a dead empty item. `measure` can't see it — the card bottom is unchanged — so it survives to print. Concrete bad case (prior session): an OPT-AIL banner loop label `↻<br>repeat<br>$K$ iters` rendered as `repeat` and `K iters` jammed onto one row instead of three stacked lines.

`polish` warns **LAYOUT/FLEX-BR** when any flex/inline-flex element has a direct `<br>` child, reporting the computed `flex-direction` so the fix is obvious. **Fix:** wrap each line in its own `<span>` (or `<div>`) and set `flex-direction: column` with `align-items: center` / `text-align: center`; or, if the element doesn't need to be flex, make it a plain block where `<br>` works normally. Never rely on `<br>` for layout inside a flex box.

### Gate E — Header logos (affiliation / venue) & title squeeze

Logos live in the header, outside any card or hero panel, so Gates A–D never see them. The failure modes are real and silent: a 404'd logo prints **blank**; a wide wordmark rendered at seal height becomes enormous and **squeezes the title** (the header grid is `1fr minmax(50%, auto) 1fr` — the title sits in an equal-tracks-centred column floored at 50%; an oversized **right** block is caught by the right-block ratio, and either-side imbalance by the title-offset gate, below); a transparent dark mark **vanishes** on a dark header; a white-background JPG leaves a **stray white rectangle** on a colored one.

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
- **HEADER/TITLE-SQUEEZED** — the right block (`.right-block` / `.right-stack`) exceeds `--rightblock-max-ratio` (default **32 %**) of header width, or the title block drops below `--title-min-ratio` (default **45 %**). The right-block ratio is the live signal (individual logos can each pass while their sum still crowds the title — this catches the sum). The title-min floor is now mostly a legacy / custom-header guard: the shipped header floors the centred title track at 50 % (`1fr minmax(50%, auto) 1fr`), so a normal title never measures below 45 %. Fix: shrink/stack the side blocks or drop an asset.
- **HEADER/TITLE-OFFCENTER** — the title-block centre sits more than `--title-offset-max` (default **6 %**) of header width off the poster's centre line: one side block (logo / venue badge / QR) outweighs the other, so the centred title track is pushed aside (a fat **left** venue badge counts too — this is the one Gate E signal that sees left-side imbalance). This is the centring trade-off made visible. **Proper logo/QR sizing and a clean layout come first** — rebalance the header (shrink, stack, or move the heavier side, or widen the lighter side) only when you can do it *without* shrinking the logo/QR below a legible size. Otherwise accept it; centring is best-effort.
- **HEADER/OVERFLOW** — a header block's box spills past the header's content edge by >2 px: the side blocks are too wide to sit beside the title at its 50 % floor, so the row overflows (and clips) instead of shrinking the title. This is the case the ratio + offset gates miss — two large but *balanced* side blocks keep the title centred and each side under 32 %, yet the row still doesn't fit. Fix: shrink, stack, or drop a side block. (Measured on box edges, not block-vs-title overlap — a title-block floored at 50 % is intentionally wide, so its box can abut a neighbour without the visible text colliding.)

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
12. **Title: prefer one line.** Size the title from the `--fs-*` scale so it fits the centred title track on a *single* line; accept a 2-line wrap only when one line would force an illegibly small font or break a phrase awkwardly. A gratuitous wrap costs scan-speed and first-impression impact — a one-line title reads as more finished. When it genuinely must wrap, **balance** it (`text-wrap: balance`, already the title default) so neither line is a lone word or a `*`-marked fragment (see **Gate B — lone wrapped fragment**). Priority: a clean one-liner first; a *balanced* two-liner when one line costs too much; never a ragged two-liner that strands a lone marker-prefixed word on its own line.
13. **Stat / metric tiles: vertically center content, never top-align.** A row of small tiles (`.keybox`, or a hand-rolled metric grid — e.g. tiles like `4+1 / 0 / F1·Acc·EM·mCC` where one label is far longer than the rest) stretches every tile to the tallest one; with default block flow the numbers then sit at unequal heights and read ragged in the small boxes. The shipped `.keybox .kb-item` now centers its content (`display:flex; flex-direction:column; justify-content:center`); **for any custom tile grid do the same**, so a 1-line tile's number lines up with a 2-line neighbour's instead of floating at the top.
14. **Portrait footer is narrow — keep each block to one line.** The footer is a two-block flex row (`method·venue·ack` | `code·contact`) pushed apart by `space-between`; in a sub-A1 portrait the right block's repo URL + email overflow the edge or wrap into a ragged stack — the recurring "messy bottom strip". Keep it clean: let the **QR carry the long link** and print only a short repo path (`github.com/org/repo`, no `https://`), drop a bulky `Acknowledgements:` line if it bloats the row, and lean on the shipped defaults (`flex-wrap` + `overflow-wrap:anywhere` on `.repo`) that break a long token and stack the blocks rather than overflow. If both blocks still won't fit side by side, let them stack — a clean two-line footer beats a clipped one-liner.

## When to call an external LLM reviewer (three checkpoints)

The skill works fine without one, but a second pair of eyes reliably catches paper-to-poster fidelity bugs you'll otherwise discover next to the print station. Three natural checkpoints:

1. **Content critique** (Step 1.5) — does the poster's prose / numbers / claims match the paper?
2. **Theorem & equation pass** (after Step 3) — are theorem preconditions complete? Equations rendered correctly?
3. **Final polish** (Step 6.5) — fresh eyes on the assembled poster for residue and overclaims. Strengthen this into a true **final gate**: run it **cross-model** (a different model family than drafted the poster) on the *final artifacts only*, after `run_gates.py` is all-green — see **§Enhanced gates & fix discipline → Cross-model final review**.

The bias is **send when uncertain**. Cost: 2-3 min. Cost of a silent error in a poster you'll print and stand next to for 2 hours: high.

**Recommended reviewer settings (if you have Codex MCP):** `model="gpt-5.5"`, `model_reasoning_effort="xhigh"`, `sandbox="danger-full-access"` (read-only review; the sandbox often fails to start in containers / nested namespaces and the audit is read-only anyway). Any other capable reviewer LLM that can `Read` paper files works equally well — see Step 1.5 for the canonical prompt template.

## Tools

```
tools/
├── poster_check.py        ← CLI: measure / preflight / polish / verify-final
├── render_preview.py      ← CLI: print-emulated PDF + thumbnail PNG
├── run_gates.py           ← orchestrator: preflight→style→asset→measure→polish → GATE_REPORT.json   (vendored, ARIS)
├── style_check.py         ← HARD style gate: token-only colors, no inline style, font/size scale     (vendored, ARIS)
├── asset_check.py         ← real-figure provenance gate (data-source + FIGURE_MANIFEST)               (vendored, ARIS)
├── extract_pdf_figures.py ← pull real figures from a paper PDF (contact-sheet / auto / crop)          (vendored, ARIS)
├── preprocess_figures.py  ← autocrop / resolution-check crops, keep the manifest honest               (vendored, ARIS)
└── _posterly/             ← internal modules (canvas parser, Playwright + settle, etc.)
```

The five `(vendored, ARIS)` tools are layered enhancements documented in **§Enhanced gates & fix discipline** below (license/attribution in `NOTICE.md`); they reuse posterly's own `_posterly` engine. The core flow uses only `poster_check.py` + `render_preview.py`:

- `poster_check.py`:
  - `measure` — **hard** alignment gate (column-bottom spread < 5 px, gap-to-footer in [30, 50] px, intercard gap in [12, 50] px inside each column, canvas-fill ∈ [95 %, 101 %] as a coarse diagnostic, and poster bbox aligns to the page within ±2 px — the bbox-alignment check is the authoritative full-canvas requirement).
  - `preflight` — static HTML lint (LaTeX residue, math `<`, missing images, role validation).
  - `polish` — **soft** visual gate (figure sizing by AR, broken images, typography orphans, space-between fill, `<br>`-in-flex collapse, header logos: broken / oversized / QR mismatch / title squeeze). Warns by default; `--strict` to fail. Hard-fails if the poster has no `[data-measure-role]` markup at all (silent PASS would be a worse bug).
  - `verify-final` — `pdfinfo`-based PDF sanity (page count, dimensions, file size).
- `render_preview.py` — Playwright print-emulated PDF + scaled PNG thumbnail.

All scripts read `@page { size: W H }` from the input HTML so the same code handles ICML 60×36 landscape, ICLR 24×36 portrait, CVPR A0, etc. without flags.

## Enhanced gates & fix discipline (vendored from ARIS)

These tools and the fix discipline below are vendored from ARIS's `paper-poster-html` (MIT © 2026 wanshuiyin — see `NOTICE.md`). They layer on top of the Step 4 / Step 6 gates and reuse posterly's own `_posterly` engine. All are **optional enhancements** — the core Step 0–7 flow stands on its own.

### One-shot gate runner — `run_gates.py`

Instead of calling `measure` / `preflight` / `polish` by hand each iteration, run all gates in their load-bearing order and get the whole fix surface in one report:

```bash
# core gates (preflight + style + measure + polish):
python tools/run_gates.py poster.html --report GATE_REPORT.json
# add --manifest to also run the real-figure asset gate (see below):
python tools/run_gates.py poster.html --manifest FIGURE_MANIFEST.json --report GATE_REPORT.json
```

Order is fixed: `preflight → style → asset → measure → polish`. The cheap static gates (preflight/style/asset) run before the expensive renders (measure/polish), so a structural or style bug fails fast instead of burning a render. `GATE_REPORT.json` holds every gate's pass/fail + findings — one read tells you the whole fix surface. Child processes run with `sys.executable`, so it uses the same interpreter/venv as posterly. Plain `poster_check.py measure` still works if you don't adopt the style/asset gates.

Without `--manifest`, the asset gate is **opt-in** — it is reported `NOT_RUN` and excluded from `overall` (real figures not verified), so a green `overall` means *the gates that ran* passed, not that figures were checked. (This is a posterly fix to the vendored orchestrator — see `NOTICE.md`; upstream silently counted the missing-manifest asset gate as a pass.)

### Style HARD gate — `style_check.py`

The Step 6 `polish` gate is *soft* (aesthetics). `style_check.py` is a **hard** gate for the design-system discipline the templates assume:

```bash
python tools/style_check.py poster.html        # add --tokens <pack.json> if you use one
```

13 rules: colors only via `var(--…)` from the `:root` token block (no stray hex), no inline `style=`, no gradients, font-family against a whitelist, font-size only from the `--fs-*` scale, bounded token count, the `data-*` / inline-SVG contracts, and (rule 13) every `block--modifier` variant class used in the markup must have a matching CSS rule — a dropped rule leaves the class inert and the layout silently wrong (e.g. a `keybox--4` with no `.keybox.keybox--4` rule falls back to the 3-col base grid, orphaning a 4th tile into an empty second row). Pure static analysis plus a small Playwright render gate for computed-style rules, so it's cheap — run it right after the Step 3 scaffold and on every layout change.

> **Note.** `style_check` assumes a *tokenized* template — a `/* ===== DESIGN TOKENS ===== */ … /* ===== END DESIGN TOKENS ===== */` block, colors via `var(--…)`, sizes via `--fs-*`, no inline `style=` / gradients. posterly's `*_neutral.html` templates **are** tokenized (vendored from ARIS — see `NOTICE.md`), so a poster scaffolded from them passes `style` out of the box. A hand-written or imported non-tokenized template will FAIL `style` until you tokenize it; the other gates (`preflight` / `measure` / `polish`) don't require tokenization. (Note: the older posters under `examples/` predate tokenization and will not pass `style` — they're showcase artifacts, not templates.)

> **Reconciling with the older layout examples.** Several examples in *Step 6 / Visual polish gates* below use inline `style=` — figure widths (`style="width: …"`) and the per-poster logo-size override near the Gate E tables (`style="--logo-h: …; --logo-wmax: …"`). `style_check` (rule 2) forbids inline `style=` **except** on `img[data-source="paper"]` (the `width: NN%` opt-out) and inside the `data-color-exempt="logo"` subtree. So if you adopt `style_check`: express figure widths via the `w-95` / `w-100` utility classes (see `templates/COMPONENTS.md`) or a tokenized component rule; and keep the logo override inside the `data-color-exempt="logo"` subtree (where it's exempt) or move it to a tokenized class — rather than taking the bare inline-`style=` snippets literally under the hard gate.

### Real-figure provenance gate (optional) — `asset_check.py` + figure tools

Step 1–2 already says "use real figures, ≥2× resolution". This gate *enforces* it for the workflow where you want a hard guarantee that every paper figure is genuinely from the paper (not AI-fabricated, not a tiny decorative thumbnail). **Needs the `figures` extra**: `pip install -e ".[figures]"` (PyMuPDF + Pillow).

1. `python tools/extract_pdf_figures.py paper.pdf --out fig_work/ contact-sheet` → a labelled page grid to read crop bboxes off; then the `auto` (candidate regions) and/or `crop` subcommands at 300–450 DPI (the top-level `--out` goes **before** the subcommand). **A human confirms crop choices** (🚦).
2. `python tools/preprocess_figures.py fig_work/fig.png --autocrop --manifest FIGURE_MANIFEST.json` → trims white margins, checks resolution, and (with `--manifest`) re-syncs each crop's `natural_px` / `sha256` so the manifest stays honest. Without `--manifest` it autocrops but leaves stale hashes that `asset_check` will then reject.
3. Embed as `<img data-source="paper" data-asset-id="fig1">`; record each in `FIGURE_MANIFEST.json` (page, bbox, dpi, sha256, natural_px, `from_paper: true`).
4. `python tools/asset_check.py poster.html --manifest FIGURE_MANIFEST.json` → fails unless ≥2 paper figures resolve to manifest entries with matching sha256 and adequate rendered area. Theory-only papers waive the total-area rule at a human checkpoint (`--waive-total-area`), never silently.

If you don't adopt this contract, skip it — the other gates don't require `data-source` / manifest markup.

### Fix discipline — softened closed-set fix vocabulary

The failure mode of any "render → review → fix → re-render" loop is the **patch loop**: the agent fixes one nit by adding an inline style / a new hex / a one-off SVG, the next gate flags *that*, and it never converges. The discipline below keeps the Step 6 loop bounded. It is the **softened** form of ARIS's closed set — half-closed, with a smooth escape hatch — suited to posterly's human-in-the-loop use:

- **Prefer the named knobs.** Every fix inside the loop should be one of the 7 operations catalogued in `templates/COMPONENTS.md` (edit a `:root` token; swap/add/remove a catalogued component; rebalance paper-sourced content; reselect template/canvas; edit a component's token-only CSS; toggle a predefined variant; fix an asset). These are *named, reusable* knobs, not one-off hacks.
- **No one-off hacks.** No new inline `style=`, no new hex anywhere (colors come from tokens), no bespoke decorative SVG, no single-element font-size override — `style_check.py` enforces these as hard rules.
- **Escape hatch (the softening).** If a fix genuinely needs something outside the catalog — a new token, variant, or component — the agent may **propose** it explicitly, flagged as a *system extension* for your review, rather than being hard-blocked. On approval, add it to `COMPONENTS.md` / the token block and re-run from Step 3 so it passes `style` from a clean state. Don't splice a new element into a mid-loop poster silently.
- **Round caps are a guide, not a wall.** Default: ≤3 issues per round, and after ~3 rounds without reaching your visual bar, stop patching and escalate (reselect template/content, or a human call) rather than endless cosmetic micro-tuning. Adjust the caps deliberately — you're in the loop.

### Cross-model final review (strengthens Step 6.5)

Step 6.5 becomes a true **final gate** when run after `run_gates.py` is all-green and polish warnings are zero-or-waived: open a **fresh, cross-model** thread (a different model family than drafted the poster — e.g. Codex `gpt-5.5`, `xhigh`) on the *final artifacts only* — `poster.html`, the rendered PDF/PNG, the paper source, and `GATE_REPORT.json` — passed as **paths, no executor framing**. It re-checks fidelity/overclaims on the *polished* text (polish introduces new claims), residue (`\ref{`, `TODO`, raw `<` in math, missing images, remote URLs), visual rhetoric (headline numbers prominent, banner readable at 2 m), and gate-log coherence. The reviewer *recommends*; it does not edit. Any fix loops back through Step 4/6 — never straight to re-review.

## Templates

See `templates/README.md` for the gallery. Current set (all **tokenized** — pass `style_check` as shipped):
- `landscape_4col_neutral.html` (60×36 in, 4 cols)
- `landscape_hero_neutral.html` (60×36 in, hero + supporting col)
- `portrait_2col_neutral.html` (24×36 in, 2 cols)

Adding a template: keep it neutral (no lab branding), preserve the `data-measure-role` scheme, tokenize it (DESIGN TOKENS block + `--fs-*` scale, colors via `var(--…)`, no inline `style=` / gradients) so it passes `style_check`, and document the row in `templates/README.md`.

## Key rules

- **Never invent paper numbers.** Read the `.tex` source. Bench numbers, datasets, model names — all verifiable.
- **Card-shadow visibility is non-negotiable.** A poster looks cheap when shadows are clipped.
- **Strict alignment is non-negotiable.** Spread < 5 px or it's not done — do not report success until `measure` exits 0.
- **Preserve user-judgment decisions across sessions.** "Do not revert" notes (`✉ stays on Author X`, `α-sensitivity card removed`) — re-read the user's prior messages before "improving" a section.
