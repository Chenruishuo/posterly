---
name: posterly
disable-model-invocation: true
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

The skill is venue- and lab-neutral by default. Compose a design direction from `templates/DESIGN-AXES.md` (Step 2.5), scaffold from the nearest template in `templates/README.md`, edit `:root` design tokens to match the locked direction, fill TODO placeholders with your paper's content.

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

Don't pick colors, logos, a QR target, the text density, or the block count silently. Ask the user in one round. (The template and the overall look are deliberately NOT asked here as a text question — they are decided in **Step 2.5**, where composed candidate directions are shown as rendered thumbnails; this round gathers that step's inputs.) AskUserQuestion takes at most 4 questions per call, so if more than four of the topics below need input for this poster, send the four most decision-relevant first and ask the rest (usually QR and block count) in a brief second call:

- **Style leanings**: "Any look-and-feel must-haves or vetoes? E.g. 'keep it light', 'a dark editorial look is welcome', 'no mascots' — or 'no preference'." Do NOT ask the user to pick a template or a style from a text list here: the layout skeleton and the whole visual direction are composed in **Step 2.5** and chosen there by eye from rendered thumbnails. This bullet only collects constraints for that composition.
- **Palette**: "Lab/venue colors? E.g. `#XXX` accent + `#YYY` highlight — or say 'you pick'." When the user gives colors, use them as the palette seed. When they don't, do **not** silently fall back to the one house style: derive a poster-specific palette from the materials at hand (**§Palette derivation** below). Either way the palette is then *shown, not just named* — it lands in the Step 2.5 thumbnail candidates, where the user can veto it cheaply. The shipped neutral (steel-blue accent + warm-gold register) is the *last-resort* fallback, not the default.
- **Logos & venue mark**: "Any logos to place? Affiliation / lab logo, and the conference / journal logo — give paths or URLs, or say 'none'." Don't assume a venue logo is wanted; cross-check the logo policy from Step 0 (some venues forbid them). When logo files are provided, inspect each one (aspect ratio, transparency, background — Step 2 item 5) and pick a size class + chip treatment per **Gate E — Header logos** below; don't just drop them in at the default size.
- **QR code**: "Want a QR code? If so, pointing at which link — paper / arXiv / code repo / project page — or none?" Generate it **offline** as a local image (see Customizing in README / `qrencode`); never leave a remote QR-service URL in the poster — it hangs `measure`'s networkidle wait and link-rots in print/archive.
- **Text density**: "How much text should the poster carry? (a) **Normal** (default) — posterly's usual concise balance of prose and paper figures; (b) **Light** — fewer words, with the saved space reassigned to paper-sourced figures/diagrams across the poster." For **Light**: trim secondary prose and merge or drop low-value text cards *only* when the freed area becomes visual real estate — larger AR-appropriate figures, figure-dominant cards, or additional useful paper visuals. Keep multiple figures while each stays legible; do **not** concentrate the budget into one enlarged centerpiece or switch layouts for that reason. "More room" means larger, clearer visual regions — never blank columns / cards / gaps: the Step 4 `measure` gate and the Step 6 anti-whitespace / figure gates all still apply.
- **Block count**: "How many content cards should the poster split into? (a) **Normal** (default) — the usual number of cards per column; (b) **Fewer** — fewer, larger cards for a calmer, less subdivided poster." This is **orthogonal to text density**: it controls how the content is *boxed*, not how much there is. For **Fewer**: consolidate related material into fewer, larger cards (merge adjacent cards that share a theme, fold a thin card into its neighbor) — keep every load-bearing section, number, equation, and figure; **merge and enlarge, never delete** substance, and don't shrink type to fit. Still fill the canvas — fewer cards means each card and its figures grow into the freed space; no blank columns / cards / gaps, the same `measure` and anti-whitespace gates apply.

Persist the user's answers as you go — re-reading them later prevents "improvement" loops that revert deliberate decisions.

### Palette derivation (when the user has no color preference)

A paper already carries brand signals — the default palette should be **derived from them, not house-styled**. Pick the seed color from whichever signal is strongest for *this* poster (judgment call, no fixed priority):

- **Affiliation brand color** — the official identity color of the dominant lab/university (your own knowledge or a quick web check: Tsinghua purple, MIT cardinal, ETH blue…). Strongest choice when one affiliation dominates the author list.
- **A provided logo** — extract its dominant saturated color (snippet below).
- **Venue identity** — if the conference has a recognizable brand color.
- **The paper's own figures** — dominant hue of the headline figure; the poster then echoes its figures.
- **Field/topic conventions** — weakest signal; use only when nothing above gives a usable color.

Whatever the source, the seed feeds one fixed recipe — the rebrand surface is the same eight tokens in every template (`--accent`, `--accent-deep`, `--accent-light`, `--accent-soft`, `--accent-ink`, `--emph`, `--emph-soft`, `--emph-ink`):

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
# --accent-ink stays #FFFFFF -- the AA loop above just guaranteed it.
# 3) Emphasis register: pick --emph per the rule below, then derive
#    --emph-soft = mix(emph, white, 0.90) and check --emph-ink (the ink
#    used ON the emph fill; template default #14314A) still
#    clears 4.5:1 against the register you chose -- swap it if not.
```

Rules that hold regardless of seed source:

- **Print-safe accent**: muted-to-medium saturation, medium-dark value. The AA loop above enforces the dark end; if a brand color is neon-bright, mute it toward the template's tone rather than shipping fluorescent ink.
- **Emphasis register (`--emph`) is a per-poster choice, not a fixture**: it is the single "ours / best" cue (the `.ours` row, `★` callouts, `.keyword-emph`), and defaulting it to the same color on every poster is a recognizable fingerprint. Pick ONE register per poster from a shortlist that suits the accent — warm gold `#C9A24A` (classic against cool accents), deep cool slate `#3D4A5C` (safe on any accent), rust `#A2521C`, forest `#2D5F3E`, burgundy `#8F2437` (see `templates/THEMES.md` for the calibrated pool) — and vary the choice across posters. Constraints: (a) hue-distinct from the accent (rule 4 allows exactly these two hue families); (b) if the accent is warm (red/orange/yellow), the register must be cool; (c) re-derive `--emph-soft` as the register's ~90% white tint and keep `--emph-ink` at 4.5:1 on the register fill. (These constraints govern the default accent+emph role topology — a deliberately different Axis 3 choice made in Step 2.5, e.g. same-center tonal or categorical roles, follows `templates/DESIGN-AXES.md` instead.)
- **Backgrounds default to near-white** (`--bg-page`/`--bg-card` untouched, or at most a faint seed-hued tint) — this recipe derives the *accent* tokens, not the ground. A non-white canvas (cream / light tint / brand hue / near-black) is a legitimate **Axis 2** choice made in Step 2.5, with its own contrast obligations (`templates/DESIGN-AXES.md` clash rules 6 and 9) and, for dark grounds, the `"dark_ground": true` declaration in the `--tokens` JSON (Step 2.5 item 4).
- **Echo the choice**: state the seed source and final tokens to the user (they surface visually in the Step 2.5 thumbnails) and record them in the Step 2.5 `DESIGN DIRECTION` comment block — "accent #660874 from Tsinghua brand; register slate #3D4A5C" — so a later edit doesn't "correct" a deliberate derivation back to neutral.

### Step 1 — Confirm content & figures

With the venue spec and design-discovery answers in hand, ask once:
- **Source paper** path (`paper-overleaf/.../main.tex` ideal). Read the abstract, intro, headline results. Don't draft from memory — pull actual numbers, dataset names, equations.
- **Figures**: match `images/` filenames to paper figures.
- **Corresponding-author marker**: which author gets `✉`? Any starred (`★`) co-authors?
- **Items to preserve/exclude**: which sections to drop, any "do not revert" notes.

### Step 1.5 — Content audit (mandatory; external reviewer recommended)

**When to run it:** this audits a *filled draft*, so do it once you've scaffolded (Step 3) and put real content into `poster.html` — but **before** you sink renders into the Step 4 measure/balance loop. It sits here, numbered with the content steps, because fidelity is a *content* concern, not a layout one: catching a wrong number now costs nothing, catching it after the layout loop wastes every render in between. The same audit repeats on the *final* poster at Step 6.5.

The draft must be audited for paper-to-poster fidelity. Past sessions caught real bugs ONLY here — paper said "20× fewer" but the table gave 16×, "fewest trajectories" was an overclaim vs the actual baselines, theorem preconditions were silently dropped. Skip this and you will discover errors only when standing next to the printed poster.

**How to run it (in order of preference):**

1. **External LLM reviewer with file access (best).** If you have Codex MCP, GPT-5 with file access, another Claude session, or any reviewer that can `Read` paper source files, use that. Recommended defaults if you have Codex MCP: `model="gpt-5.6-sol"`, `model_reasoning_effort="xhigh"`, `sandbox="danger-full-access"` (read-only audit — the sandbox often fails to start in containers / nested namespaces, and the audit only reads files anyway). Send the evidence pack + reviewer prompt below.

2. **Self-audit (fallback).** Walk every numeric claim on the poster and find its `file:line` in the paper source. Build the claim → evidence table by hand. Slower, easier to miss things, but better than skipping.

**Evidence pack the reviewer needs:**
1. The current `poster.html` (full)
2. Paper source path(s) so the reviewer can `Read` the `.tex` and any `results/` CSVs
3. For every numeric claim, the paper `file:line` where the number originates
4. For every theorem/claim, the paper statement verbatim with all preconditions

**Reviewer prompt template** (use this verbatim, fill bracketed parts):

```
Audit the academic-poster draft at [poster.html abs path] against the paper at [main.tex abs path] (and any results in [results dir]). For every number, claim, theorem, dataset name, method-comparison, AND the author block (author order, affiliations, corresponding-author marker vs \icmlcorrespondingauthor / \thanks, grant number) on the poster, produce a claim → evidence table:

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
3. **Re-export at ≥ 2× the rendered px** — the print-quality *target* (the `asset` gate's hard floor is a lower **1.5×**, so a 2× source clears it comfortably). A `200u × 120u` figure print-rendered at 96 ppi → ~756 × 454 px. Source PNGs must be ≥ 1500 × 900 to look crisp at print.
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

### Step 2.5 — Design direction (compose → thumbnails → lock)

Layout skeleton, canvas, palette, typography — every look-and-feel choice — is made **here**, as one composed direction, before any template is copied. The menu is `templates/DESIGN-AXES.md` (8 orthogonal axes, a devices pool, clash rules); the rendered option catalog is `specimens/axes/index.html` (one page per axis). This step sits after Steps 1–2 because two axes depend on knowing the content: density (Axis 5) is a capacity decision, and an Axis-1 focal choice needs to know the headline figure.

1. **Concept first, then compose per axis.** Start each direction from a **concept statement** — one line naming the world the poster lives in ("engineering blueprint — annotated schematic on grid paper", "midnight editorial", "archival index card"); the recipe names in `DESIGN-AXES.md` §Recipes are ready-made concept statements, free to adopt or adapt. Then for each of the 8 axes pick a *primary option + modifiers* (an axis choice is a structured object, never a bare enum pick), plus 0–2 devices from the pool — each pick **derived from the concept**: if you can't say in one phrase how a pick serves the concept, it's decoration — swap it for one you can, or default that axis to quiet. A merely-legal combination that serves no concept is exactly the "assembled, not designed" look this step exists to prevent. Feed in the Step 0.5 answers: user/derived colors → the Axis 3 seed (**§Palette derivation**); text density and block count → Axis 5; style vetoes → hard constraints. Then walk the clash rules at the bottom of `DESIGN-AXES.md`: check all 9 **hard** rules one by one against the composed set (check, don't debate); a **soft** rule you trip stays legal, but write the tradeoff down in one line — e.g. "cream canvas + grotesque type: accepted, the letterspaced eyebrows carry the editorial tone". Finally, every direction designates its **hero moment** — the single loudest element on the sheet (an oversized headline number, a statement masthead, a dominant hero figure, one full-bleed band; usually the Axis 1 focal choice or one device doing double duty). Exactly one: two competing loud elements read as noise, zero reads as an unfilled template. Everything else sits at least a register quieter, and in the Step 4–6 space fights the hero moment is not the first thing you shrink.

2. **Compose 2–3 candidates, far apart.** One direction is a proposal, not a choice — compose 2–3 so the user actually chooses. Candidates must be distinguishable at thumbnail size: **every pair must differ on at least two of the five fingerprint axes** — layout skeleton (Axis 1), canvas base (Axis 2), frame-line (Axis 6), section-heading joint (Axis 7), masthead (Axis 8). Two candidates that differ only in accent hue are the same candidate twice. Tag every candidate with its build cost before showing it: (a) current templates/components realize it directly; (b) it needs a construction ported from the `specimens/axes/` catalog (the token-native CSS exists but must be adapted to the poster's tokens and units, not pasted — normal); (c) it needs a brand-new system component — offer it only with that caveat, and a user pick of a (c) candidate is a direction *preference*, not yet the lock: raise the Step 6 escape-hatch system-extension proposal first, and lock/scaffold only once it's approved. Never show the user a thumbnail you can't build.

3. **Thumbnail pre-selection.** For each candidate build a quick *style specimen* — NOT a full poster: one small HTML file with a masthead bar plus one column of 2 cards, applying that direction's canvas, palette, typography, frame-line, and section-heading joint (placeholder copy is fine; no figures, no `@page`, no `data-measure-role`). If the direction's hero moment is a visible structure (statement masthead, giant stat, full-bleed band, dominant figure), sketch it as one *abstract* placeholder block at roughly its true relative scale — a flat grey box stands in for a figure — so the user isn't picking the loudest element blind. Likewise, whenever the layout skeleton is among the fingerprint axes on which a candidate pair differs, each of those specimens must also carry a mini page-wireframe — flat grey blocks laid out in the candidate's actual grid at the canvas aspect ratio, à la `specimens/axes/axis1_layout.html`, ~150 px tall — so the skeleton difference is *visible* at thumbnail size, not just claimed. Render each to a small PNG with Playwright — same file-URI → screenshot pattern as `tools/render_preview.py`, only simpler: a fixed viewport (~800×1000 px) and `page.screenshot()`, no print emulation, no PDF. Specimens are throwaway working files (`direction_a.html` / `direction_a.png` in the work dir — never in `templates/`) and run **no gates**: no `run_gates.py`, no `measure`, no `polish` — they exist only to be looked at.
   - **Interactive session**: show the PNGs, then ONE AskUserQuestion — one option per candidate (short label + the candidate's concept statement and hero moment as its one-line sketch) plus "none of these — recompose". For an (a)/(b) candidate the pick is the lock; a (c) pick is a direction preference — run the Step 6 escape-hatch system-extension proposal first and lock only on approval.
   - **Non-interactive session**: lock the recommended candidate yourself and state why (fit to content volume, venue tone, wave-level anti-convergence) in your report.

4. **Lock and record.** Record the locked direction as an HTML comment block that goes at the top of `poster.html` the moment Step 3 scaffolds it (and stays there through every later edit) — axis by axis, with modifiers, devices, and the anchor poster IDs you leaned on:

   ```html
   <!-- DESIGN DIRECTION (Step 2.5, locked)
     concept:        cream editorial -- a journal front page: serif masthead, framed plates, rust accents
     axis1 layout:   3-column, top-hero (focal: pipeline figure)     [62396, 66579]
     axis2 canvas:   cream, flat, full                               [64736]
     axis3 palette:  accent+emph; accent #0F6070 (lab-logo seed), emph rust #A2521C
     axis4 type:     serif display + sans body; small-caps eyebrows  [64736]
     axis5 density:  balanced
     axis6 card:     white surface, thin colored frame, shadow       [65714]
     axis7 heading:  underline rule + number chip                    [65287, 63757]
     axis8 masthead: brand band; footer: contact strip               [63030]
     devices:        metric scoreboard, QR CTA
     hero moment:    top-hero pipeline figure -- the one loud element; scoreboard stays a register quieter
     soft-clash notes: none tripped
   -->
   ```

   Then write the tokens pack — **always**, named `design_tokens.json`, next to `poster.html`, holding at minimum the accent/emph hue centers — and pass it on every gate run as `run_gates.py … --tokens design_tokens.json` (forwarded to `style_check.py`):
   - **hue centers** (`"hue_centers": {"accent": <deg>, "emph": <deg>}`) — rule 4 reads exactly these two slots and allows at most two non-neutral hue clusters. Dual-semantic: map the two semantic hues onto the accent/emph slots and a re-enabled rule 4 checks clean. Categorical (3+ hue roles): rule 4 *cannot* pass and must stay disabled (it is off by posterly default, `--style-disable 4,5`) — record the full palette in the `DESIGN DIRECTION` block instead;
   - **vendored font families** (`"fonts": {"serif": […], "sans": […], "mono": […]}`) when the Axis 4 voice is off the built-in whitelist (vendor the files locally, never a CDN);
   - **`"dark_ground": true`** iff the Axis 2 base is near-black or a dark brand hue: it switches off style rule 12's large-dark-area warning, which is calibrated for light posters and would otherwise fight a deliberate dark ground. Never set it on a light poster to silence a rule-12 warning about an oversized dark slab — there the warning is reporting a real problem.

**Anti-convergence.** The shipped default (4-col landscape / 2-col portrait skeleton · white canvas · soft card · plain headings · centered masthead) is one combo among many, not the home position: landing there after a fresh composition is fine; landing there every time is a fingerprint. In a **wave** (several posters in one batch), consecutive posters must differ on at least two of the five fingerprint axes (layout skeleton / canvas / frame-line / section-heading joint / masthead) and must not reuse the previous poster's concept statement — read the previous poster's `DESIGN DIRECTION` block before composing the next, and hold the `--emph` register decision at wave level per `templates/THEMES.md` Mechanism 1. **A single poster gets the full treatment too — this machinery is not wave-only.** Compose the candidates just as far apart, and treat the default combo as a pick that must *earn* the lock like any other: locking it requires a one-line reason in the `DESIGN DIRECTION` block naming what it serves (venue conservatism, a user veto on decorated styles, a content volume only that skeleton fits — "nothing spoke against it" is not a reason). When no candidate has earned the lock over the others, prefer the one with its own look over the home position: default-by-inertia on a lone poster is the same fingerprint, one poster at a time.

### Step 3 — Scaffold from the gallery

1. `cp templates/<chosen>.html <work-dir>/poster.html` — `<chosen>` is the template whose skeleton is nearest the locked direction's Axis 1 topology (`templates/README.md` table); the remaining axes are applied on top as token edits and component swaps.
2. Paste the `DESIGN DIRECTION` comment block (Step 2.5) at the top, then edit the `:root` design tokens (single block; affects everything) to realize the locked direction — palette (Axis 3), typography (Axis 4), density scale (Axis 5), frame/radius tokens such as `--rs` (Axis 6). The figure mount belongs to that same Axis 6 decision: restyle `--fig-bg` / `--fig-frame` with the cards so paper figures sit *in* the design instead of pasted on it (transparent-PNG ground + keyline; captions already run on `--text-secondary`, block-figure caption `<strong>` additionally on `--accent-deep`).
3. Replace `<title>`, header (title/subtitle/authors/affiliation), banner (if any), column cards, takeaways strip (if any), footer. **Author metadata is copied, never assumed**: verify author order, affiliations, the corresponding-author `✉` (against `\icmlcorrespondingauthor` / `\thanks` / the author footnote in the paper source — a wave-2 poster shipped the `✉` on the first author while the paper marks the last), and any grant number, each against the source; if the source doesn't mark a corresponding author, omit the `✉` rather than guess.
4. Match the template's `data-measure-role` scheme — DO NOT remove these attributes. The measurement script depends on them.
   - **Custom skeleton? Carry the BASE DEFENSES.** When the locked Axis-1 topology needs a skeleton the templates don't ship (band-rows, a display-title spine, …) and you write the stylesheet from scratch or heavily rewrite it, copy the templates' `BASE DEFENSES` CSS block (marked with that comment in every `*_neutral.html`) into the new sheet and extend its selector lists with your custom prose/display classes: `text-wrap: pretty` on every prose class, `text-wrap: balance` on *centered* display text (title, takeaway lines — never on left-aligned multi-sentence prose), and for any inline class that paints a background (highlight marks, keyword chips): declare its own `color` — never inherit across grounds (Gate G) — plus `box-decoration-break: clone; -webkit-box-decoration-break: clone;` so a wrapped highlight keeps its padding on both fragments (then it never needs `&nbsp;`-gluing to stay on one line). **When you rebuild the `.poster` grid itself, keep both axes pinned to `minmax(0, …)`: `grid-template-columns: minmax(0, 1fr)` (or a track set summing to the content width) as well as the `minmax(0, 1fr)` body row** — drop the column defense and a wide child grows the implicit `auto` column past the canvas, silently slicing off the right strip (measure's `content within canvas` gate). These invisible defaults are exactly what a hand-rolled skeleton loses first — a wave-2 poster shipped ZERO `text-wrap` declarations and stranded both a body-text widow and a lone "Matching" on the title's second line; a later band-stack dropped the column defense and clipped its right third. `polish` warns (`TEXT-WRAP`) when ≥3 wrapped blocks lack protection. **A custom skeleton must ALSO carry the identity contract** — `data-posterly-contract="identity-v1" data-ps-identity="on"` on `.poster`, the `#psReg` sprite (`.ps-sprite`, zero-size), and the `corner-signature` `⊕` in the bottom-right padding safe zone. `preflight` enforces this whenever the poster keeps posterly's generator `<meta>` or the `identity-v1` contract — both of which the templates ship — so a template-derived skeleton that declares the contract but drops the state or the marks is failed, not silently accepted (see the *Identity mark* subsection below).
5. **No logo / QR provided:** keep the venue as its **text** badge — don't fabricate a venue logo. With no affiliation logo, **delete the empty `.logo-slot`** rather than leave a hollow box; the text affiliation line carries attribution. With no QR, delete `.qr-block`. Never fetch or invent an asset the user didn't give, and never leave a remote QR-service URL in the poster (offline local image only). (The legacy `.ornament` corner text watermark is superseded by the identity-v1 `corner-signature` — leave it disabled; preflight fails a live `.ornament` under an active identity contract.)
6. **The takeaways strip is optional — judge it deliberately; don't default to keeping it *or* to cutting it.** The landscape scaffolds ship with a bottom takeaways strip, but it earns its place only as a genuine 60-second narrative exit (3–4 one-line slots; the classic Idea / Method / Result / Practical labels are one example set — reword per the microcopy rule below). Keep it when it lands a conclusion the final column cards don't already; **delete the whole `.takeaways-strip` block** when those cards already close the argument or it would just restate the body — a redundant strip is worse than none (portrait templates omit it by design). **When the poster is over-full** — content fighting to fit, font sizes creeping toward the venue's floor, cards cramming together — this strip is the *first* block to drop to win the body its room back, and you should reach for that readily: cutting a merely-adequate takeaways row makes a better poster than shrinking everything to keep it. But the call is about *content*, not pressure: don't delete a strip that genuinely closes the poster just because space is tight, and don't keep one that isn't carrying its weight. Same spirit as *"Fill means substance"* below: a block stays only if it does real work. **Hero exception (applies to this strip and the framework banner alike):** a block that is the locked **hero moment** loses automatic first-cut status, and removing it — for *any* reason, content-merit or space — is a change to the locked direction, not a layout fix: in an interactive session ask the user to confirm the removal and the replacement hero (their pick was the lock); in a non-interactive one re-designate the hero yourself in the `DESIGN DIRECTION` block and record why.
7. **The framework banner is optional too — same deliberate judgment, applied to the top.** A poster does not *have* to open with a `FRAMEWORK` / TL;DR strip. Keep the `.framework-banner` only when the paper genuinely compresses to one sentence plus 2–4 headline numbers worth reading from 2 m. If the contribution doesn't reduce to a single line, or the opening is better carried by a hero figure (`landscape_hero`) or by the first column itself, **delete the whole `.framework-banner` block** and let the body grid absorb the height (then rebalance through the Step 4 measure loop). A banner that merely paraphrases the title or pads generic stats is noise at the poster's most valuable position — worse than none. **When content is overflowing, this banner is likewise among the first things to cut** — it holds the most valuable real estate for often the least load-bearing content, so reclaiming it for the body is usually the right trade and you shouldn't hesitate (a banner that *is* the locked hero moment follows the **hero exception** stated under the takeaways strip above: no automatic first-cut status, and removal only via user confirmation when interactive, recorded self-re-designation otherwise). Still, judge on merit, not pressure alone: a true one-line TL;DR with live headline numbers can be worth keeping even on a tight sheet. **A method figure in the banner usually needs no caption** — the banner's text block beside it already explains the method, so a figcaption just says it twice, and a long one is exactly what stretches the figure slot and strands the image with a dead band beside it (`polish` flags this as `BANNER/IMAGE-SLOT`). Default to a **captionless** `banner-figure` (`<figure class="banner-figure"><img …></figure>` — see COMPONENTS.md), never a hand-rolled `.fb-fig` or a bare `<img class="w-100">`. If a figure genuinely needs panel labels, bake them into the image or keep them to **one short** `<figcaption>` line (the component bounds the caption to the image width); centre a block image with `margin-inline:auto`, not `text-align:center`.
8. **Microcopy is placeholder, not canon.** The scaffold's small fixed words — the banner eyebrow, the takeaways strip title and slot labels, the QR label, the footer labels, the section names, the ★ key-marks — are stubs and examples, not house style: reword them to the poster's voice and concept (an "engineering blueprint" poster might label its exit strip "Field notes" and its eyebrow "Spec"). The old fixed set — eyebrow "Framework", strip "Takeaways: Idea/Method/Result/Practical", QR "Paper & Code" — shipping verbatim on every poster is a *textual* fingerprint, which is why those are now `TODO` stubs. Section names come from the paper's content: generic slots (Motivation, Method, Main Result) are fine anywhere, but the scaffold's distinctive ones (Key Insight, Why It Works, Numbers at a Glance) are examples to replace, not defaults to keep. In a wave, consecutive posters must not reuse each other's microcopy set.

**Emphasis discipline (copy-level de-fingerprinting).** Bold in body copy is earned per phrase, not budgeted. The test: *must a reader 2 m away catch this in a 3-second scan?* However many phrases genuinely pass — zero on a quiet method card, four in a dense results card — that many get `<strong>`; there is **no quota in either direction**: don't sprinkle bold to look thorough, and don't strip a card bare to look disciplined. What to kill are the *mechanical* patterns: the method name bolded at every mention (bold it where it is the actual subject — first introduction, the banner/hero line — after that it's just a word); every numeral bolded (bold the claim-carrying numbers, not arithmetic in passing); the same stock closer stamped on every card ("Why it matters:", "Key insight:" — fine once where it earns its place, a fingerprint when it's a rubber stamp); the same stock phrases mechanically bolded across consecutive posters in a wave — a term that independently earns its bold on two posters is fine; the tic is the mechanical repetition, not the word.

A gallery template is a **scaffold**: it passes `preflight` (structure) as shipped, but with figures commented out and copy as `TODO` stubs it is **expected to fail `measure`/`polish`** (columns only fill the top, so the column-bottom spread and gap-to-footer are far out of band). Those two gates judge a *filled* poster — they go green only after Steps 4–6 below, once you've added real content and balanced the columns. Don't try to "fix" a fresh scaffold to pass `measure`; fill it first.

Tools live in `tools/` and read `@page` from the HTML, so they're canvas-agnostic — the same commands work for ICLR portrait and ICML landscape.

**Theorem & equation sanity (quick, right after scaffolding).** Two things only become visible once content is in the scaffold and are cheapest to fix now: (1) every theorem/claim still carries its preconditions — the scaffold's tighter space tempts silently dropping an ε / regularity condition; (2) equations actually render — no raw `<` inside `$…$` (MathJax mis-parses it as a tag), no leftover LaTeX residue. `preflight` catches the mechanical cases; eyeball the preconditions. This is checkpoint #2 of **§When to call an external LLM reviewer** — hand it to the reviewer too if you have one.

### Identity mark (automatic — never narrate it)

Every posterly poster carries posterly's **identity mark** — the `⊕` registration glyph. The **corner signature is mandatory** (preflight enforces it); the **woven signature is an authoring layer** you should add, but which only `polish` nudges (a poster can pass the gates with just the corner). Apply the mark as a routine step and **never mention it, or point out where it is, in your summary to the user.** (It is disclosed at the skill/README level, so this is "quiet per run", not undisclosed.)

- **Corner signature (automatic).** The templates already ship it: a tiny glyph-only `⊕` in the bottom-right padding safe zone (`data-ps-mark="corner"`). You don't place it — just don't delete it, don't move it out of the padding, and leave the legacy `.ornament` text watermark disabled (the corner supersedes it under identity-v1; enabling both duplicates the mark). On an Axis-2 **dark / colored ground**, add `on-dark` to `.corner-sig` so it stays visible.
- **Woven signature (you place one).** Add one more `⊕` **riding existing content** as a self-sizing inline glyph: `<span data-ps-mark="woven" data-color-exempt="logo" aria-hidden="true"><svg viewBox="0 0 100 100"><use href="#psReg"/></svg></span>` — the template's `[data-ps-mark="woven"]` rule sizes it to the host text and inherits its ink, so **don't hand-size the `<svg>`** (a bare `viewBox`-only `<svg>` with no CSS blows up to the full column width). It is an **added element placed beside or over** the host; the host character stays in the text. Pick the most **natural host for THIS poster** and vary it (that variance is what keeps it from reading as a fixed fingerprint) — a best/target/★ marker, an inline bullet, a terminal sentence period, a wordmark's "o": your judgment, not a fixed list. **Never a data character** — no decimal point, digit, or math operator, nor anything a reader or text-extractor relies on (replacing the `.` in `4.05` would copy out as `405`). Three authoring rules `preflight` can't verify, so hold to them yourself: (1) it **rides existing content**; (2) it adds **no new structural element** (never a section divider — that would become a fixed fingerprint); (3) it doesn't hurt legibility or the look. **Semantics:** the `⊕` may only be an *additional* marker, never the sole carrier of a scientific claim — keep any "this row is best / this is the target" meaning readable from the text or table styling, then add the `⊕`.
- `preflight` HARD-checks exactly one corner (and at most one woven); `polish` softly nudges if the woven mark is missing. Both sit under the poster root's `data-posterly-contract="identity-v1" data-ps-identity="on"`.

**Anonymous submission.** If Step 0 found the venue forbids identifying marks (or the user asks for none), set `data-ps-identity="off"` on the `.poster` root and remove BOTH marks (and make sure no legacy `.ornament` lab watermark is enabled — that would leak an identifying mark too) — decide this **up front**, because pulling a woven `⊕` riding a period later changes copy / line-wrap and forces a full gate re-run. With `off`, preflight HARD-requires zero `data-ps-mark`s (the gate can't pass while the PDF stays marked).

### Step 4 — Render + measure loop (HARD GATE)

**Default driver: `run_gates.py`.** After every layout change, run the whole sequence in one shot — `preflight` → `style` → `measure` → `polish` in load-bearing order (plus the `asset` gate only when you pass `--manifest`; otherwise it's reported `NOT_RUN` and excluded from `overall`), into one `GATE_REPORT.json` (see **§Enhanced gates & fix discipline**):

```bash
# After every layout change (the default loop driver). The Step 2.5 pack
# (design_tokens.json, always written at lock time) rides on EVERY call —
# dropping it silently un-declares your fonts / hue centers / dark_ground:
python <skill>/tools/run_gates.py poster.html --tokens design_tokens.json --report GATE_REPORT.json
```

**Before the first loop iteration — run `pack` once (advisory).** A column whose figures *at their Gate A floors* still overflow the footer-gap window — or *at their ceilings* still can't reach it — cannot be fixed by figure sizing at all, and discovering that inside the loop costs many wasted rounds. `python <skill>/tools/poster_check.py pack poster.html` probes both endpoints in the browser and names the column: `REPACK_RECOMMENDED` (move a card out / trim text before looping) or `FIGURE_ONLY_UNDERFILL` (the residual needs content, not figure growth). It is advisory (exit 0; floors are polish's WARN thresholds, not physical minima; hero panels aren't modelled) — treat it as the "should I re-pack cards across columns first?" answer, then enter the loop.

**The loop is budgeted (script-enforced circuit breaker).** `measure` counts **consecutive failed measurements** in an on-disk file next to the poster (`.<filename>.posterly_budget.json`, e.g. `.poster.html.posterly_budget.json` — survives context compaction); the first PASS, 12 h idle, or `--reset-budget` clears it. At the cap (default **30**, `--measure-budget`, 0 disables) `measure` exits **3** with a `CIRCUIT BREAKER` banner and refuses to render again: stop iterating, re-think the layout (re-pack via `pack`, or reselect template/canvas) or escalate to the user with the current best state rendered — do NOT `--reset-budget` just to keep grinding the same edits. `run_gates.py` surfaces exit 3 as a measure FAIL and skips the remaining gates.

**Work from the failure report, not the file.** On a spread/gap/intercard failure, `measure` now prints (a) the **shared passing band** — the one bottom-range every column must land in — with per-column `grow/trim ~N px [safe +lo..+hi]` deltas, and (b) an **edit targets** block listing every card per column with its source line (`L<n>`), height, and a text anchor, marking the bottom card that sets the column bottom. Iterate from that report: jump to the source line or Grep the anchor, read the surrounding block to confirm you have the right card, edit, re-run. Don't re-`Read` the whole poster.html every round (the anchors are math-stripped locators, not verbatim source), and never emit the full file through your output (scaffold via `cp`, then surgical `Edit`s). Full re-reads stay legitimate where they earn their cost: first contact with an unfamiliar/custom template, a cross-column re-pack, a structural/nesting failure, an anchor that's missing or ambiguous, and the final claim audit.

This is what wires the **`style`** hard gate into every iteration — the standalone `measure` call below does **not** run `style`. posterly runs `style` with rules **4 (≤2 hue families) and 5 (no gradients) disabled by default**: palette and gradient choices are yours, while the rest of the design-system discipline stays enforced. Override with `--style-disable ''` to enforce all 14, or e.g. `--style-disable 4,5,6,7` to also drop the font rules.

The standalone `measure` call is the **minimum fallback** — a quick single-gate spot check; it skips `style`/`asset`:

```bash
# Minimum / spot-check only (no style, no asset):
python <skill>/tools/poster_check.py measure poster.html
# Same single browser launch, plus the advisory polish report:
python <skill>/tools/poster_check.py measure poster.html --with-polish
```

`--with-polish` runs the polish measurement on the **same rendered page** (one Chromium launch instead of two) and prints its report at default thresholds. It is **advisory there** — it never changes `measure`'s exit code; the loop's final soft gate remains a standalone `polish` run (`--strict` if you want it enforced).

Targets (defaults; configurable via flags):
- **`spread < 5 px`** across the last-card-bottoms of all columns (+ any hero panel). Aim `< 3 px`.
- **`gap to footer-strip/footer ∈ [30, 50] px`** — card shadow visible but cards don't float.
- **`intercard gap ∈ [12, 50] px`** — whitespace between consecutive stacked cards inside a column (side-by-side cards count as one row). The ceiling catches `justify-content: space-between` faking bottom alignment on an under-filled column: spread reads ~0 and the footer gap lands in band while a void sits mid-column (observed in the wild: 98–135 px voids against a 22.7 px design row-gap). The floor catches cards packed so tight the drop shadow (`0 2u 6u` in shipped templates) is buried under the next card, fusing the stack into one slab. Tune via `--max-intercard-gap` / `--min-intercard-gap` (floor 0 to disable for shadowless themes).
- **`position align ≤ 2 px`** (authoritative) — the `[data-measure-role="poster"]` bounding box must sit at `(0, 0)` to `(viewport_w, viewport_h)` within `--position-tol-px`. This IS the full-canvas requirement: a poster whose bbox aligns to the page is necessarily full-bleed. Catches `transform: translate*`, mis-positioned `position: absolute`, stray body margin in print, and CSS source-order cascade bugs where a screen rule wins over a print override.
- **`canvas-fill ∈ [95 %, 101 %]`** (coarse early diagnostic) — `[data-measure-role="poster"]` width/height ratio against the print viewport. Fires before the position check when the ratio is FAR off, with a more diagnostic error message that points at the common `@media print { :root { --u: 1mm } }` omission (renders at ~42 %) or hardcoded `width > @page` (renders at >100 %). For borderline 95–99 % cases, position-align is the truth. Tune via `--min-canvas-fill` / `--max-canvas-fill`. **Safe-area design** belongs as internal padding on a full-bleed `.poster`, NOT as a smaller poster — a smaller poster fails position-align.
- **`content within canvas`** (hard) — the poster BOX can be exactly the right size and origin while its CONTENT is wider or taller than the canvas and gets sliced off at the page boundary — the poster box stays 24×36 in while a right (or bottom) strip of every full-width row vanishes in print. The two checks above read the poster *box*, the clip gate reads only card/column/hero/band, and the spread/gap gates read vertical bottoms, so nothing else catches this. The gate compares the poster's `scrollWidth/Height` (which includes the overflowing content in **both** overflow modes — `hidden` clips it at the poster, `visible` spills it past the page) against its client size; MathJax's 1 px-clipped a11y nodes don't inflate it. (`scrollWidth/Height` grows for overflow past the **right/bottom** edge — the direction this bug produced; content shoved off the *left/top* by a negative offset is clipped without inflating it and is NOT caught here — position-align catches a grossly displaced poster, a left-bled child inside a correctly-placed poster stays an eyeball check.) **The classic cause: a `.poster` grid with `grid-template-rows` but no `grid-template-columns` — the implicit `auto` column grows to a wide child's max-content and every full-width band overflows.** Fix: pin the column axis with `grid-template-columns: minmax(0, 1fr)` (the shipped templates now carry it in the `.poster` rule — see the *Custom skeleton? Carry the BASE DEFENSES* note in Step 3; a custom skeleton must too), or find the fixed-width child (a table, a `width:` in the wrong unit, an un-wrapped `nowrap` line) forcing the layout wide. This was a live miss: a portrait band-stack rendered its whole content at ~1.5× canvas width with `overflow:hidden` silently clipping the right third — every other gate green.

**This gate is non-negotiable.** If `measure` exits non-zero, fix the layout — do NOT continue to render. Common fixes:
- spread > 5: shrink the column with the lowest last-card by reducing a paragraph's `margin-bottom` by 1u, trimming one line, or shrinking a fixed-height figure by 5u.
- intercard gap > 50: an under-filled column is being stretched. Remove `justify-content: space-between`/`space-around` from the column, use a fixed `gap`, and absorb the slack with CONTENT (grow a figure, add paper-sourced text per Gate C) — never with whitespace. The same rule holds for **any track** — a masthead spine, side rail, or footer strip (`polish` flags those as `TRACK/INNER-VOID`; see **Slack in a track** under Gate C).
- intercard gap < 12: an over-full column is being squeezed by shrinking the row-gap, which buries card shadows. Restore the design `gap` (6u ≈ 22.7 px) and take the height back out of content instead (trim a paragraph, shrink a figure by 5u, or move a card to a shorter column).
- gap > 50 everywhere: body-grid is too tall; grow a card with substance (per Gate C / *Fill means substance*) or reselect a smaller canvas — don't leave the whitespace.
- gap < 30 anywhere: banner/header outgrew its slot; check `.framework-banner` rendered height.
- position misaligned (the usual full-canvas failure): make `.poster` full-bleed (`width: 100%; height: 100%; margin: 0; padding: 0` in `@media print`); remove any `transform: translate*` or `position: absolute` offsets; ensure `html, body { margin: 0; padding: 0 }` in the print media query; and check that the print `@media` block comes AFTER the screen `.poster` rule so source-order cascade resolves the print override winning.
- canvas-fill < 95 % (diagnostic fired first): poster forgot `@media print { :root { --u: 1mm } }` so it renders at screen scale. Add the override.
- canvas-fill > 101 % (diagnostic fired first): hardcoded `width: 1600px` (or similar non-`--u`-based size) exceeds `@page`. Replace with `calc(N * var(--u))`.
- content overflows the canvas (right/bottom strip sliced off): the `.poster` grid is missing `grid-template-columns` — add `grid-template-columns: minmax(0, 1fr)` so the single content column can't grow past the canvas; or hunt the fixed-width child (table, wrong-unit `width:`, `nowrap` line) forcing the layout wide.

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

Beyond defect-hunting, hold the render against its own `DESIGN DIRECTION` block once: at thumbnail size the locked hero moment should be the first place the eye lands (a competing loud element is a quiet-it fix in Step 6, not a redesign), and the sheet should still read as its concept statement rather than as parts from different posters.

**Identity mark — check it by eye.** On the same render, crop the bottom-right corner and confirm the `⊕` corner-signature actually PAINTS: a crisp ring + crosshair at glyph scale, visible against its ground (add `on-dark` on dark grounds). If a woven `⊕` is placed, confirm it reads as a small inline glyph riding its host — not a blown-up block, not a blank gap. On an anonymous poster (`data-ps-identity="off"`), the same look must confirm **no** `⊕` anywhere. The gates verify *structure*, not *paint* — a stray style on the `<use>`, an exotic SVG nesting, or a deformed glyph can pass every static check while rendering wrong or blank — so this eyeball is the paint-level gate. A missing/blank/distorted `⊕` means the sprite or mark markup drifted: restore it verbatim from a template before Step 6.

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

**Step 6.5 — Final review (strongly recommended)**: once `run_gates.py` is all-green and polish warnings are zero-or-waived, send the rendered PDF (or its high-res PNG slices) AND the HTML to the same kind of reviewer used in Step 1.5 (external LLM if available, self-audit otherwise). Same evidence-pack rule. The reviewer prompt focuses on four things distinct from Step 1.5:
1. **Visual rhetoric**: does the poster's narrative carry? Are the headline numbers prominent? Is the framework banner readable from 2 m?
2. **Residue**: any `\ref{`, `\cite{`, leftover `TODO`, raw `<` in math, missing image, broken QR link.
3. **Final claim audit**: re-check numbers and overclaims AFTER content has been polished — polish often introduces new claims ("a key advantage of…") that were not in the original draft.
4. **Design coherence** (judgment questions, not a restyle mandate — include the poster's `DESIGN DIRECTION` comment block in the evidence pack): Does the rendered sheet deliver its own concept statement, or do some elements read as pasted in from a different poster? Is the locked hero moment actually where the eye lands first, and is it the only loud element? Do figures sit mounted in the design — each component's *native* mount (ground / keyline / caption where the component has them) consistent with the direction — rather than dropped on top of it? Two component contracts the reviewer must not "fix": the hero-panel img is frameless by design (its stage frames it), and a banner figure is usually captionless. And do the small words and the bolding speak *this* poster's voice — or the scaffold's ("Framework" / "Takeaways" verbatim) and a formula's (the same words bolded on every card, one stock closer stamped throughout)? On emphasis there is no quota in either direction — zero-bold and several-bold cards are both legitimate; the question is only whether each bold earns its place. A miss here is almost always a small fix — retune a token, quiet one competing element, re-mount one figure — never grounds for a redesign. The locked direction and the venue's legibility floors outrank the reviewer's taste: in particular, discard generic "make it bolder" advice (bigger display type, louder colors, added ornament) that isn't answering one of these questions.

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

**Upstream feedback (default behavior).** If the run surfaced a defect or rough edge in posterly itself — a gate false positive/negative, a template bug, a misleading instruction, a tool crash you worked around — keep a note of it during the run, and after delivering the poster ask the user whether to open an issue or PR against the posterly repo (https://github.com/Chenruishuo/posterly). Bring the specifics (exact gate output, minimal repro, or proposed patch); file nothing without the user's go-ahead.

## Visual polish gates (Step 6 — soft gate)

Alignment passes but the poster can still look amateur. The failure modes below (Gates A–E, plus the framework-banner image-slot gate `BANNER/IMAGE-SLOT`) recurred across sessions enough to be promoted to first-class checks. `tools/poster_check.py polish` surfaces each as a WARN; the rules below explain how to fix.

### Gate A — Figure sizing by aspect ratio

A figure too small for its column is more wasteful than one too big. Pick width by the figure's intrinsic aspect ratio (`AR = naturalWidth / naturalHeight`), NOT by a fixed default:

| AR range | Shape | Aim for | `polish` warns below / above |
|---|---|---|---|
| `AR > 1.3` | Wide (workflow diagram, comparison chart) | **90–100%** of card width when the figure owns its card; 70–85% only when it genuinely shares the card with meaningful text | < **65%** ⇒ FIG/WIDE (the defect FLOOR, not the target). Avoid image-left/text-right in a narrow column — text gets squeezed to nothing (deliberate, balanced exception: the `data-fig-layout="beside-text"` opt-out below). |
| `0.8 ≤ AR ≤ 1.3` | Square-ish (block diagram, scatter) | **55–75%** of card width | < **55%** ⇒ FIG/SQUARE. |
| `AR < 0.8` | Tall (multi-series bar, long pipeline) | **45–60%** (centered if text-sparse, **wrapped** if text-rich) | < **36%** centered ⇒ FIG/TALL-SMALL (small + side voids); > **70%** ⇒ FIG/TALL. |

The 90–100% aim for figure-dominant cards is **field-calibrated**: ResearchStudio's paper2poster ran a live poster wave at a 70% floor and still shipped visibly under-filled "small stamp in a big card" figures, then raised its gate to 90%-on-one-axis. posterly keeps the WARN floor at 65% because its cards legitimately mix text and figure (their cards are figure-dominant sections) — treat the floor as "definitely a defect below this", and the 90–100% band as where a figure that *is* the card's payload should land.

Thresholds are tunable via `--wide-min-ratio` / `--square-min-ratio` / `--tall-max-ratio` / `--tall-min-ratio`. The defaults bracket the documented "aim for" range, so a figure inside it passes cleanly. `--tall-min-ratio` (default **0.36**) is a *hard floor, not the ideal* — a centered tall figure rendering below it (≈ a 64%+ symmetric side void) is the recurring "figure too small" bug; the ideal is still 45–60%. The floor is measured as **rendered width ÷ card width**, which runs a few points below the CSS `width:%` (card padding), so calibrate against the rendered figure, not the style value. Because `polish` is soft, a borderline figure you've consciously accepted can keep its WARN; raise the floor and run `--strict` if you want it enforced.

A figure whose `<img>` fails to load (missing file, 404, or unreachable remote URL) reports zero natural size and warns as **FIG/BROKEN** — it will be blank in print. An SVG legitimately reports zero intrinsic size, so it's exempt from FIG/BROKEN — but the AR sizing gates **still apply to it**, computed from its **rendered** aspect ratio (so a too-small/too-wide SVG figure is not silently exempt). The probe covers both card and hero-panel `<img>` (the hero centerpiece is the worst image to silently lose). One known gap: an SVG served from an extensionless URL still slips the FIG/BROKEN exemption heuristic (gets wrongly flagged broken).

**Hero figures aren't exempt from sizing — HERO/STAGE-LETTERBOX.** The card-width AR gates above (FIG/WIDE etc.) don't apply to a hero panel, but a hero figure can still waste its space: a narrow-aspect picture dropped into a wide-but-**short** `.hero-stage` is height-constrained and strands itself with big symmetric side voids (a 2:1 panorama height-capped in a 5:1 stage fills ~35 % of the width). **HERO/STAGE-LETTERBOX** fires when the picture fills < 55 % of the stage width *while* the stage is much wider (relative to the image AR) than the image needs, with symmetric voids. The usual root cause is cramming a second large figure into the hero so the main figure loses vertical budget — move the secondary diagram into a card / the supporting column, or constrain the stage width toward the image's aspect ratio. A genuine full-bleed hero (image AR ≈ stage AR, picture fills the width) never trips it.

**A wide, short footer-strip can reclaim its title-row height — the `vrail` modifier.** When a bottom band is wide and short and a horizontal title row eats height the body could use, move the title into a **narrow left rail** so the body takes the full strip height. This is the content-agnostic `vrail` modifier (COMPONENTS.md): it suits any wide-short full-width band — a *row of small example figures* (a benchmark / task gallery) is the common case (the figures enlarge), but any other wide-short band you author works the same — a metrics row, say. The `.num` badge stays upright on top and the title's words **stack one per horizontal line** (every word reads normally — never rotated/sideways), centered, which also evens out uneven word lengths. An over-long word is broken with a soft hyphen `&shy;` at a sensible syllable point **you (the agent) judge** — not `hyphens: auto`, which no-ops in the headless renderer and lets the word overflow. Mark the title `data-vrail-title` so the deliberately narrow stack is exempt from the WIDOW check. **Only on a wide, short, full-width strip** — never a narrow column card, where the rail eats scarce horizontal width instead of freeing it (a title too long to fit without several hyphenations is the signal to shorten it or stay horizontal).

Concrete bad case (prior session): `co-consideration.png` (AR ≈ 1.41) shipped at 41 % column width. The whitespace beside it conveyed nothing and the figure was unreadable from 2 m. Fix: 66 % width, no text-right.

**Deliberate image-left/text-right (the opt-out).** FIG/WIDE fires on a wide figure sized below 65 % because the *usual* cause is the bad case above — a figure shrunk into a gray margin. But a wide figure that **shares its card with a meaningful text column** (figure left, explanatory annotations right) is a legitimate layout when the text genuinely earns its space and isn't squeezed to a sliver. For that case, mark the `<img>` with `data-fig-layout="beside-text"`:

```html
<img src="images/dynamics.png" alt="Training dynamics"
     data-fig-layout="beside-text" class="w-100">
```

This skips the AR width gates (FIG/WIDE / FIG/SQUARE / FIG/TALL / FIG/TALL-SMALL) for that image only — **FIG/BROKEN still applies** (a blank image is a bug regardless of intent). The attribute records the design decision *in the markup*, so a later edit (human or agent) reads "this figure is intentionally beside text" and leaves the layout alone instead of widening it to silence the warning. Use it only after you've eyeballed the render and confirmed the text column isn't squeezed — it is an opt-out for a *verified-good* layout, not a way to mute a real warning.

**Center vs. wrap a tall figure (AR < 0.8).** A tall figure is *too small* just as easily as too wide — shrunk to ~35 % and centered it's illegible with a big symmetric side void on each margin (the recurring bug `FIG/TALL-SMALL` now catches below a 36 % rendered width). Which layout to use is driven by **how much text shares the card**:

- **Text-rich card → wrap** the figure: text flows *beside and below* it, so the image can be large. Float it with `.fig-wrap` / `.ff-fig` (shipped in every template) and mark the `<img>` `data-fig-layout="beside-text"`. The figure **and** its surrounding text must live inside one `.fig-wrap` — the clearfix is what makes the card grow to contain the float; a bare floated `<img>` escapes the card box and `measure` then reads the wrong card bottom.

  ```html
  <div class="card" data-measure-role="card">
    <div class="section-title"><span class="num">N</span><span class="st-text">…</span></div>
    <div class="fig-wrap">
      <figure class="ff-fig w-50">
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

`polish` flags an element (`[class*="stat"], [class*="num"], .takeaway-num, .hs-stat, .headline-num`) — emitted as `ORPHAN` — only when its text **ends with a whitespace-separated trailing glyph** from `↑↓↔×÷±§¶†‡*°%` and lacks `white-space: nowrap` — i.e. a lone glyph token that could wrap by itself, like `1.18–1.30× ↑` or `18.24% ↓`. It does **not** catch fused forms such as `4096 × 4096`, `7 nm`, `2248×`, `BraVE*`, or `MEAN§` (the text doesn't end on a space-separated glyph) — guard those by hand with the defenses above.

**Lone wrapped fragment — display text that wraps to a short, stranded last line.** The orphan logic extends from stat numbers to *any short display text that wraps* — a title, `.section-title`, banner headline, or one-line takeaway whose break strands a short fragment alone on the final line. The worst case is when that fragment is a **word carrying a leading footnote/superscript marker** (a `*`- or `†`-prefixed term): stranded and left-aligned, the marker+word reads as a stray symbol or a typo, not a word. `polish` **does** catch this now (`WIDOW`) — at the full ~35% bar for the whitelisted prose classes listed here, and at a conservative **single-stranded-word** bar for *every other wrapped text block*: candidates are discovered by geometry, not class name, so a custom skeleton's own classes (a `.mh-sub` masthead subtitle, a `.band-lede`) are covered — the wave-2 lone-"Matching" title strand was exactly such an unlisted block. A *centered* heading/title is evened by `text-wrap: balance` (the generic single-word bar now backstops it) — and the framework-banner body (`.fb-text`), centered yet fully gated (it uses `text-wrap: pretty`, not balance), is held to the higher fill bar described below. It measures wrap geometry on `.callout`, `.body-text`, `.caption`, `.section-title`, `.card p`, `.card li`, `.fb-text` (framework-banner text) — including each `<br>`-delimited segment — and warns when the last visual line fills **less than ~35% of the typeset width** (the widest line of the block). **Exception — the framework banner (`.fb-text`):** as the poster's single most prominent text block it carries a much higher bar (**~80%**) — its last line must nearly **fill** the measure so the banner reads as a clean *filled rectangle*, not a ragged box. The fix is to **reflow** it to a near-full last line — use any one, or a **moderate combination**, of these *parallel* levers (no fixed order): **(W) width** — tune the `.fb-text` flex ratio against `.banner-stats` (the fill jumps **non-monotonically** with width — e.g. one real poster went 17%→97% between two nearby ratios — so try a few), *without* starving the stat boxes; **(F) font size** — bump `.fb-text` one `--fs-*` step, which (when it shifts the wrap) reflows the text and makes the most-prominent block bolder, *without* overflowing the banner or colliding with the stats; **(E) expand** — add a few truthful, on-message words so the last line grows to fill (no fabricated claims, and keep `.fb-text` under the ~400-char display cap — past it the gate only judges a single stranded word, not banner fill); **(T) trim** — cut a few words so the block settles into one-fewer line that's all full and the runt disappears, without dropping a load-bearing number/term. Keep the change **proportionate to the gap** — don't push one lever to an extreme (a blown-up font, a starved stat strip) just to clear the %. Never force it with `text-align: justify` / `text-align-last` or `letter-spacing` padding (those strand ugly gaps / fake a rectangle the eye still rejects). After any fix, **re-render and look** — clearing ~80% is necessary, not sufficient. It judges by the last line's **width**, not its word count: a *short two-word* tail (`= OMAD-only.`) flags just like a one-word one, while a *single long word* that fills the line does **not** (its width ≈ the measure — it isn't stranded). Limits (still guard by hand): math/figures no longer hide a whole block — they join the line model as opaque cells. A last line trailing a **figure/icon/table** (`img`/`svg`/`canvas`/`table`), or one that is **purely a lone equation** (a trailing equation/figure with no real word, even with a sentence period — `…by $\lambda$.` has the word "by" and IS judged), stays unjudgeable; but a short text tail ending in inline **math** (`mjx-container`, e.g. `…traded off by $\lambda$.`) **is** caught — judged by its full visual width, math symbol included. It still skips `white-space: nowrap/pre`, RTL, and elements marked `data-vrail-title` (a deliberately narrow `vrail` rail title — its short stacked lines and agent-chosen soft-hyphen breaks are intentional, not runts). Running prose over ~220 chars (display text `.caption`/`.callout`/`.fb-text`: ~400) is **no longer skipped outright** — it drops to the conservative bar: only a stranded SINGLE word flags there (the ~262-char paragraph that shipped a lone `AIME24/25).` last line in wave-2 is exactly what the old blanket skip hid). **Time widow fixes after `measure` is green.** Rewording changes the paragraph's word count, which can change its *line count* — moving that column's bottom by a whole line-height and undoing alignment you already tuned (the same edit made *before* alignment costs nothing). Once the layout passes `measure`, prefer a rewording that keeps the block's line count (swap a word for a longer synonym rather than adding one) and re-run the gates after; `balance` and `&nbsp;` glue re-break the existing lines without adding one, so they don't disturb alignment — but glue stays bounded by the two-token rule below: clearing every widow with glue is exactly how wave-2 shipped early-wrap holes (`GLUE-CHAIN` now flags ≥3 fused words), so alignment convenience never overrides the reword-first order. Fix a **non-banner** `WIDOW` (or a fused-glyph case the gate can't see) by the option that makes the lines **fill naturally**, not merely the one that silences the gate — in this order of preference (the framework banner uses the parallel menu above, not this list): (1) **reword — expand or contract the sentence** — first choice for left-aligned prose (`.callout`, `.body-text`, `.caption`): move the break to a natural phrase boundary so the last line carries more of the measure *and* the line above fills to the margin. Adding one word often does it (e.g. "expressive" → "highly expressive"). (2) **`text-wrap: balance`** on a *centered heading / title* evens the lines so no fragment is stranded (the default on centered display text — keep it; never pair `balance` with `text-align: left`, per the wrap rules above). (3) **`&nbsp;` glue** is a **last resort**: gluing the last two tokens (`…local&nbsp;optima.`) pulls the prior word *down* onto the last line and widens it above the threshold, so it now clears the gate only when it genuinely fills the line — but it still measures the *last* line's fill, never how full the line *above* is, so on left-aligned prose glue can still leave a ragged short line above with a big right-side gap. Glue is genuinely right where a token *must not* open a line: a leading footnote/superscript marker (`…&nbsp;*term`) or a tight stat cell. Hard bound: **at most two tokens glued — never a chain.** ≥3 words fused with `&nbsp;` trip `GLUE-CHAIN`: the unbreakable unit wraps early *as a whole*, ending the line above short — the wave-2 `holds length&nbsp;and&nbsp;keeps&nbsp;improving.` incident pulled "length" onto the next line while its own line still had room (stat/math/list runs like `4.05 > GRPO 3.93` are exempt). A multi-word highlight (`.mark`) that must read as one unit across a wrap needs `box-decoration-break: clone`, not glue. After any fix, **re-render and look** — a cleared gate is necessary, not sufficient. Never ship a stranded short last line, a lone `*` / `†` / `‡` fragment, or a line left half-empty by a glue "fix".

### Gate C — Content-driven balance, not space-between-driven

`justify-content: space-between` on a column is a shortcut to bottom-align last cards across columns. It works ONLY when the cards' natural heights are within ~5% of each other. When they aren't, space-between fills the delta with empty pixels — usually one giant gap in the column with the smallest content.

**Symptom**: a column with one short card followed by 25 + mm of whitespace. Reads as "this column ran out of things to say".

**Wrong fix**: shrink `gap` globally to hide the whitespace. Peers still have meaningful internal gaps; reducing them makes the others claustrophobic.

**Right fix**: FILL THE SLACK WITH SUBSTANCE until the short column is within ~5 % of its peers' natural height — a larger paper figure where one earns the space, otherwise real paper content (see *"Fill means substance"* below for the figure-vs-prose order). Content you can recover from the paper:
- Sub-claims that were footnotes or implicit assumptions
- A 2–3 bullet "challenges" or "design choices" recap
- A short caption beside a previously-bare figure

Concrete bad case (prior session): the SnipSnap Motivation column shipped with a one-line "three challenges" summary, leaving a 13 mm space-between gap. Fix: expanded into 3 bullets matching the paper's challenge framing — column balanced via content, not whitespace.

Enforcement is two-layered. `measure` **hard-fails** any column whose gap between consecutive stacked cards exceeds `--max-intercard-gap` (default 50 px, absolute) — this is the backstop that catches the space-between shortcut regardless of mechanism (added after a production poster shipped 98–135 px voids with every gate green: spread read 0.00 px because space-between pinned the last card to the bottom, and the relative polish warn below stayed silent at 4–6 % of a 36-inch column). `polish` additionally warns earlier (emitted as `SPACE-BETWEEN`), when a column with computed `justify-content: space-between` has an inter-card gap exceeding 5 % of the column's height. Tune via `--max-space-between-fill`.

**The same trap, one card.** A single card set to `flex: 1` (the standard way to make its column reach the footer and satisfy `measure`'s spread/gap gates) is measured only by its **bottom edge** — a card stretched to twice its content's height passes `measure` with spread = 0 while the lower half is blank white. `measure` can't catch it (it checks only the bottom edge), so **`polish` does**: the **CARD/TRAILING** warning fires when a card leaves more than `--max-card-trailing` (default 10 %) of its height blank below its last line of content. A green bottom-edge gate is necessary, not sufficient. Never stretch a block to create whitespace just to make the layout "fit." Fix it like Gate C — fill the slack with substance (aim ≥ ~80 % full, not 46 %): a bigger paper figure first, real paper content when the figure can't carry it, per the figure-vs-prose order in *"Fill means substance"* below; if the section is genuinely that sparse, choose a **smaller canvas** instead — a single paragraph does not belong on a 60-inch sheet. A half-empty card reads as "ran out of things to say" and is a failed poster even when every gate is green.

**The same trap, mid-card — `CARD/INNER-VOID`.** A sibling failure mode: a *row of equal-height cards* (`grid`/`flex` + `align-items: stretch`) whose contents differ in height, where the short card pins its tail — a "Why it matters" footer, a takeaway line — to the bottom with `margin-top: auto` (or `justify-content: space-*` **on the card**). The taller card sets the row height; the short card stretches to match, and the slack opens as a band **in the middle of the card** — below the last real block, above the pinned tail. Because the tail still sits on the card's bottom edge, `CARD/TRAILING` reads ~0 and stays silent, and `measure` (bottom-edge only) passes. `polish` catches it as **CARD/INNER-VOID**: for **every `.card`** — not only the `data-measure-role`-tagged ones, so an agent-authored feature band is covered too — it measures the largest vertical gap between two consecutive stacked children and warns when that gap exceeds the card's stated `row-gap` by more than `--max-card-inner-void` (default 8 % of card height) **and** an absolute `--min-card-inner-void-px` floor (default 24 px, so a sub-line gap on a small card stays quiet). Side-by-side children (a flex row, a float) overlap vertically and never count — only a real vertical void registers. **Fix it like Gate C**: fill the short card with substance (a bigger figure first, then real paper content), or — when the cards genuinely differ in length — **drop the bottom-pin / equal-height stretch** so each card hugs its own content (the footer rows then no longer align across the row, but there is no void). This was a live miss: a 3-card "Main Technical Contributions" band whose middle card carried one equation vs two in its neighbours pinned its footer with `margin-top: auto`, opening a ~14 %-of-card void between the formula and the footer — every gate green, because the band's cards carried no `data-measure-role` (so `CARD/TRAILING`/`measure` never sampled them) and the void sat mid-card (so the bottom-edge checks saw nothing). The lesson for authoring: a content block — including one in a custom feature band — should carry the `.card` class so the void gates see it, and if a row of cards will hold unequal content, do **not** reach for `margin-top: auto` + `align-items: stretch` to fake a level footer row.

**Slack in a track — `TRACK/INNER-VOID` and the type-scale lever.** A header/footer track that stacks its children vertically — a full-height masthead spine, a side rail, a footer strip of stacked rows — is neither a measure column nor a `.card`, so none of the void gates above used to see it: a wave-2 poster stretched its full-height title spine with `justify-content: space-between` and shipped two ~500 px voids with every gate green, its byline sitting in small type under all that air. `polish` now runs the same inter-child geometry on `data-measure-role="header"` / `"footer"` tracks (**TRACK/INNER-VOID**, same thresholds as CARD/INNER-VOID; it measures the largest vertical band NO child covers — a height-aligned horizontal masthead row stays quiet, but side-by-side columns vertically offset against each other, one hugging the top and one the bottom, leave a genuinely uncovered band and do register). Fix order when a track has real slack:
1. **Substance first** — content the track genuinely earns: another legend row, a mini-diagram, the fuller affiliation/contact line, a one-line reading guide.
2. **The type-scale lever, applied consistently.** Bump the track's *subordinate* text (byline, legend labels, colophon) one `--fs-*` step so the slack is spent on readability instead of air. Consistency is the constraint that keeps this from backfiring: bump a whole ROLE at once (every legend row, the entire byline group), never a single block to plug a single gap — one block enlarged in isolation ships a patchwork poster (one card's text visibly bigger than its neighbours' reads worse than the gap it fixed). If the same role appears elsewhere on the sheet (captions in the body at the same register), bump it everywhere or not at all, and never lift a subordinate role above the register that sits over it in the hierarchy.
3. **Narrow the track** and give the width back to the body grid — a spine that can't fill its height at a readable scale is too wide.
Never absorb track slack with `justify-content: space-*` / `margin: auto` stretching — whitespace is not a filler, in a track any more than in a column.

**"Fill" means substance, not word-count — and a figure is substance.** These anti-whitespace gates (Gate C, CARD/TRAILING, CARD/INNER-VOID, FIG/BESIDE-TEXT-VOID) exist to kill *empty pixels*, not to mandate dense prose. A poster is a **talk aid, not a self-contained paper**: you stand beside it, and the small details — a derivation step, a hyperparameter, an edge-case caveat — are yours to *say out loud*, not to cram onto the sheet. So the legitimate ways to fill a region are, in order: (1) a **larger, more legible figure** that earns the space; (2) **figure-only, or figure + a one-line caption**, when the figure already makes the point clearly — a self-explanatory plot does not need a paragraph restating it; (3) genuinely load-bearing prose. Reach for more text only when the *figure can't carry the point alone*. And figure legibility wins ties: if cramming text beside a figure would shrink it below what reads at 2 m, **drop the text and let the figure be big** (center it, short caption, presenter fills the rest) rather than starve the image to justify a paragraph. And if a region is *genuinely* that sparse — the figure is already as large as it should be and there is no real paper content left — the fix is a **smaller canvas** or dropping an optional block (banner / takeaways), never stretching whitespace to fill a sheet that's too big. What these gates fail is a half-empty card or a thumbnail figure marooned in whitespace — **not** a clean card whose work is done by one big figure and a few words.

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

`logo-wide` is **intentionally shorter than the QR** (≈ 68 % of its height) so a long wordmark doesn't out-mass it — that's why the QR-match gate below gives it a band instead of a strict match. The classes are starting defaults, not law: if a logo needs a height off the three classes, add a **tokenized variant class** for it — not a bare inline `style="--logo-h: …"` on `.logo-slot`, which `style_check` rule 2 flags (the inline-style exemption covers only the `data-color-exempt="logo"` element itself, not the slot wrapper that consumes those vars). Let the rendered header crop (Step 5) be the final arbiter.

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

The chip wraps the `<img>` *inside* the `.logo-slot`, so the size class still bounds the image. Multiple logos: keep them in one `.right-block` and give them the **same** size class so the strip reads level — but **height/size-class matching equalizes the bounding boxes, not the optical weight.** A dense institutional **lockup** (seal + the institution name in two or three lines — e.g. a full university-institute mark) placed next to a clean two-element corporate **wordmark** reads unbalanced even when the boxes match: the lockup's content is crammed and tiny, the wordmark's is bold and large (the box can even be the *taller* one and still read "smaller"). Two fixes, in order: **(1)** prefer each logo's **simplest form** — the affiliation **text line already prints the institution names**, so a logo that repeats the same name (often illegibly) is redundant; use the seal/mark or the wordmark alone, not the full lockup, when that form exists. **(2)** When all logos are **wide wordmarks** of differing aspect ratio (AR ≳ 2 — **not** a square seal or tall mark, which equal width would blow up; keep those height-matched), **normalize by equal *width* and stack them vertically** — `<div class="logo-row logo-stack">` (left-aligned; don't also apply the height-based size classes) — instead of height-matching in a row; equal width aligns a clean block and lets the less-wide mark grow taller. The shipped `.logo-stack` width sits under the LOGO/WIDE cap, and a stacked row is exempt from the QR-height match (it's aligned by width, not QR height). This optical imbalance is **not catchable by a geometric gate** — the bounding boxes are already balanced, so it sits below the gate's resolution (same blind spot as a captionless-banner density problem); it's an authoring judgment, make it when you place the logos. **Portrait posters: never place a wide wordmark and the QR side by side** — the narrow header can't afford both (HEADER/TITLE-SQUEEZED will fire, by design); stack them or drop one (a `logo-stack` in the portrait header auto-drops to a column **above** the QR for exactly this reason). A custom **venue logo** (inside `.venue-badge`) gets the same chip workflow and the broken-image check, but not the QR height match — it sits left of the title at its own scale.

**What `polish` checks** (all soft WARNs; venue badge: first two only):

- **LOGO/BROKEN** — a non-SVG header logo with zero natural size failed to load and will be blank in print (the FIG/BROKEN blind spot this gate closes).
- **LOGO/WIDE** — a logo wider than `--logo-max-width-ratio` (default **22 %**) of the header width crowds the title. Fix: set the right size class (`logo-wide` caps a wordmark), not a hand-tuned pixel width.
- **LOGO/QR-MISMATCH** — a non-wide logo whose height differs from the QR's by more than `--logo-qr-tol` (default **15 %**), or a `logo-wide` slot outside the **55–85 %** band of QR height. The header strip should read level. Skipped when there's no QR, for a venue logo, and for a width-normalized `logo-stack` row (aligned by width, not QR height).
- **HEADER/TITLE-SQUEEZED** — the right block (`.right-block` / `.right-stack`) exceeds `--rightblock-max-ratio` (default **32 %**) of header width, or the title block drops below `--title-min-ratio` (default **45 %**). The right-block ratio is the live signal (individual logos can each pass while their sum still crowds the title — this catches the sum). The title-min floor is now mostly a legacy / custom-header guard: the shipped header floors the centred title track at 50 % (`1fr minmax(50%, auto) 1fr`), so a normal title never measures below 45 %. Fix: shrink/stack the side blocks or drop an asset.
- **HEADER/TITLE-OFFCENTER** — the title-block centre sits more than `--title-offset-max` (default **3 %**) of header width off the poster's centre line: one side block (logo / venue badge / QR) outweighs the other, so the centred title track is pushed aside (a fat **left** venue badge counts too — this is the one Gate E signal that sees left-side imbalance). This is the centring trade-off made visible. **Proper logo/QR sizing and a clean layout come first** — rebalance the header (shrink, stack, or move the heavier side, or widen the lighter side) only when you can do it *without* shrinking the logo/QR below a legible size. Otherwise accept it; centring is best-effort. **Never buy centring with a collision.** Achieve it only *inside* the shipped grid (rebalance / shrink / stack / drop a side block) — never force the title to the middle with a negative margin, `transform`, absolute offset, or a `nowrap` title that overflows its centre track, all of which can push the title **text on top of a logo / badge**. That collision is the one Gate E failure **no gate catches** — forcing the title-block centre back onto the header centre actually *satisfies* this offset gate while the text spills into a neighbour, and HEADER/OVERFLOW only measures the row's outer edge, not title-vs-block overlap — so confirm clearance on the rendered header crop by eye. A title sitting a few % off-centre but clearly clear of its neighbours beats a perfectly centred one whose text grazes a logo.
- **HEADER/OVERFLOW** — a header block's box spills past the header's content edge by >2 px: the side blocks are too wide to sit beside the title at its 50 % floor, so the row overflows (and clips) instead of shrinking the title. This is the case the ratio + offset gates miss — two large but *balanced* side blocks keep the title centred and each side under 32 %, yet the row still doesn't fit. Fix: shrink, stack, or drop a side block. (Measured on box edges, not block-vs-title overlap — a title-block floored at 50 % is intentionally wide, so its box can abut a neighbour without the visible text colliding.)

The defaults are calibrated against the size classes, so a logo sized by the recommended class never trips its own gate. Gate E only sees logos inside the **header** (`data-measure-role="header"`) under the `.logo-slot` / `.venue-badge` class names — when restyling, keep those classes on the wrappers (a hand-rolled `.aff-logo` class makes the logo invisible to the gate). **Bare-white detection is workflow-only, not a gate** — whether a logo "sits on a non-white background" isn't robustly decidable from static analysis, so apply the chip per the table above and verify on the rendered crop; don't expect `polish` to catch a missed chip.

**Vertical-rail mastheads.** Everything above describes a horizontal masthead strip. When the `header` role is a tall narrow **rail** (a portrait title-spine masthead — DESIGN-AXES Axis 1, P5), `polish` detects it from the aspect ratio (header height > 1.5× width) and swaps the horizontal calibrations for rail checks: LOGO/WIDE caps the logo by the **rail's content width** instead of 22 % of header width, the QR height match and both TITLE-* gates are skipped (a stacked rail has no height-matched row and no horizontally centred title), and HEADER/OVERFLOW checks all four content edges (the rail's overflow axis is vertical). LOGO/BROKEN is unconditional in both modes. The polish summary prints a `vertical rail` line when the mode is active — on a title-spine poster, a *missing* line means the `header` role landed on the wrong element (and the strip calibrations are mis-firing on your rail).

### Gate G — Composed contrast (`CONTRAST`)

`style_check` verifies the token pairs you *declared*; Gate G verifies what actually *rendered*. `polish` samples every text run's foreground against the effective ground beneath it — the hit-test stack under the glyphs, alpha-composited until opaque — and warns when the WCAG ratio falls below `--min-contrast` (default **3.0**, deliberately under the 4.5 body-text AA bar: poster type is large-format and deliberate muted inks sit ~3.5–4.5, so the gate flags only unambiguous defects; raise the floor for a stricter pass).

This is the gate for the recurring incident class the declared-pair check can never see — an inline class **composed onto a ground it wasn't designed for**: a rust `--emph` lead-in inherited onto a steel-blue `.callout` fill (wave-1, 1.2:1), an inherited white digit on a pale `.mark` highlight (wave-2, `4.05` on `#CFE6E4`, 1.3:1), a dark `--accent-ink` (designed for a neon fill) on a neutral gray chip (wave-2, 1.9:1). The authoring rule that prevents all of them: **any class that paints a `background` must declare its own `color`** — never let text color inherit across a ground change; pair every fill token with its `*-ink` partner.

Limits (hand-check these on the rendered crop): text over **images, gradients, or pseudo-element fills** is unjudgeable by this model and skipped — a caption sitting on a photo or a `::before`-painted band still needs your eye; outlined/shadowed display text is skipped too (its edge contrast is engineered, not flat); so are **translucent layers** (`opacity` < 1 anywhere in the stack) and colors authored in spaces the parser doesn't read (`oklch()`/`lab()` — author tokens in hex/rgb, which the templates do). The collection ceiling is 7.0:1, so `--min-contrast` above 7 is not supported. Warnings are deduplicated by class + color pair, soft, and waivable like any polish WARN — but a sub-2:1 hit is essentially never a deliberate design; fix the token pairing rather than waiving it.

**Optional packing advisor.** With ≥3 institution marks of mixed aspect ratio, `poster_check.py fit-logos poster.html` (read-only, §Tools) computes the row arrangement that maximises the one uniform mark height and prints a paste-ready snippet — a *starting proposal*, not a decision: it equalizes bounding boxes, so the optical-weight judgment above (lockup vs wordmark, simplest form first) still rests with you. Apply by hand only if the preview reads right; adapt to size classes / `logo-stack` when its note says the height would trip LOGO/QR-MISMATCH; or skip the tool entirely and place the logos yourself. When you do apply into a content-sized zone, also stamp `data-lf-h0="<px>"` on the zone element (the CLI prints the exact value) so a later re-run measures the original space, not the collapsed packed strip.

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
12. **Title: prefer one line.** Size the title from the `--fs-*` scale so it fits the centred title track on a *single* line; accept a 2-line wrap only when one line would force an illegibly small font or break a phrase awkwardly. A gratuitous wrap costs scan-speed and first-impression impact — a one-line title reads as more finished. When it genuinely must wrap, **balance** it (`text-wrap: balance` — the shipped templates set it on `.title` in the BASE DEFENSES block; a custom masthead must carry that block itself, Step 3 item 4) so neither line is a lone word or a `*`-marked fragment (see **Gate B — lone wrapped fragment**). Priority: a clean one-liner first; a *balanced* two-liner when one line costs too much; never a ragged two-liner that strands a lone marker-prefixed word on its own line.
13. **Stat / metric tiles: vertically center content, never top-align.** A row of small tiles (`.keybox`, or a hand-rolled metric grid — e.g. tiles like `4+1 / 0 / F1·Acc·EM·mCC` where one label is far longer than the rest) stretches every tile to the tallest one; with default block flow the numbers then sit at unequal heights and read ragged in the small boxes. The shipped `.keybox .kb-item` now centers its content (`display:flex; flex-direction:column; justify-content:center`); **for any custom tile grid do the same**, so a 1-line tile's number lines up with a 2-line neighbour's instead of floating at the top.
14. **Portrait footer is narrow — keep each block to one line.** The footer is a two-block flex row (`method·venue·ack` | `code·contact`) pushed apart by `space-between`; in a sub-A1 portrait the right block's repo URL + email overflow the edge or wrap into a ragged stack — the recurring "messy bottom strip". Keep it clean: let the **QR carry the long link** and print only a short repo path (`github.com/org/repo`, no `https://`), drop a bulky `Acknowledgements:` line if it bloats the row, and lean on the shipped defaults (`flex-wrap` + `overflow-wrap:anywhere` on `.repo`) that break a long token and stack the blocks rather than overflow. If both blocks still won't fit side by side, let them stack — a clean two-line footer beats a clipped one-liner.

## When to call an external LLM reviewer (three checkpoints)

The skill works fine without an *external* reviewer — a self-audit is the mandatory floor (Step 1.5) — but a second pair of eyes reliably catches paper-to-poster fidelity bugs you'd otherwise find next to the print station. Three checkpoints, each documented at its home:

1. **Content critique** — Step 1.5 (claim → evidence audit; the canonical reviewer settings *and* the prompt template live there).
2. **Theorem & equation pass** — the quick check right after Step 3 (preconditions survived the scaffold; equations actually render).
3. **Final polish** — Step 6.5, strengthened into a cross-model **final gate** run after `run_gates.py` is all-green (see **§Enhanced gates & fix discipline → Cross-model final review**).

The bias is **send when uncertain** — cost 2-3 min, against a silent error in a poster you'll print and stand next to for two hours.

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

The five `(vendored, ARIS)` tools are documented in **§Enhanced gates & fix discipline** below (license/attribution in `NOTICE.md`); they reuse posterly's own `_posterly` engine. The **minimal fallback** uses only `poster_check.py` + `render_preview.py`:

- `poster_check.py`:
  - `measure` — **hard** alignment gate (column-bottom spread < 5 px, gap-to-footer in [30, 50] px, intercard gap in [12, 50] px inside each column, canvas-fill ∈ [95 %, 101 %] as a coarse diagnostic, poster bbox aligns to the page within ±2 px — the bbox-alignment check is the authoritative full-canvas requirement — and poster *content* within the canvas box, catching a right/bottom strip sliced off when content overflows a mis-configured `.poster` grid). On failure prints the shared passing band + per-column safe deltas and the edit-targets block; carries the consecutive-failure circuit breaker (exit 3 at the budget cap). `--with-polish` folds the polish measurement onto the same rendered page (advisory report; measure's exit code untouched) — one browser launch when a round wants both readings.
  - `pack` — **advisory** column-feasibility pre-check (run once before the loop): probes card figures at their Gate A band endpoints in-browser and reports columns unreachable by figure sizing alone.
  - `fit-logos` — **advisory, read-only** logo-zone packer (ported from ResearchStudio's paper2poster, reshaped for the human-in-the-loop idiom: it never edits the file). Measures the header logo zone (an explicit `--zone` selector overrides everything and never falls back; else `[data-logo-zone]`; else the *union* of `data-lf-h0`-stamped zones, `.logo-row`s, and standalone `.logo-slot`s, with nested candidates resolved stamp > row > slot and outer winning ties — rows/slots *inside* an applied `logo-pack` are never auto-discovered, so a re-run returns to the original zone, and a poster with one applied and one untouched zone keeps both), searches row partitions for the arrangement that maximises the ONE uniform height every institution mark shares, and prints the proposal — rows, per-mark widths, opaque-pixel fill, a paste-ready snippet — plus a note when that height would trip Gate E's QR match. **Use it critically**: the packer equalizes *bounding boxes* only; optical weight (a dense lockup beside a clean wordmark, §Gate E) is an authoring judgment it cannot make. Apply the snippet by hand only if it reads right in the preview, adapt it (e.g. swap to size classes or a width-normalized `logo-stack`), or ignore it and place the logos yourself — then re-run the gates either way. Most useful at ≥3 marks of mixed AR; for one or two logos the size classes are already the answer. **Re-run idempotency:** when you apply a proposal into a content-sized zone, also stamp the zone's pre-application height as `data-lf-h0="<px>"` (the CLI prints the exact stamp line) — an applied pack collapses the zone to its packed height, so an unstamped re-run measures only the shrunken strip and can only propose smaller; the advisor reads the stamp back (`max(stamp, live box)`, so a template-grown zone still wins) and warns when it finds an applied pack without one.
  - `preflight` — static HTML lint (LaTeX residue, math `<`, missing images, role validation, `.figure` blocks missing their one-line `.caption`).
  - `polish` — **soft** visual gate (figure sizing by AR, broken images, typography orphans, space-between fill, card trailing / mid-card voids, `<br>`-in-flex collapse, header logos: broken / oversized / QR mismatch / title squeeze). Warns by default; `--strict` to fail. Hard-fails if the poster has no `[data-measure-role]` markup at all (silent PASS would be a worse bug). Its measurement half also rides `measure --with-polish` (same rendered page, advisory there); this standalone run remains the loop's final soft gate.
  - `verify-final` — `pdfinfo`-based PDF sanity (page count, dimensions, file size).
- `render_preview.py` — Playwright print-emulated PDF + scaled PNG thumbnail.

All scripts read `@page { size: W H }` from the input HTML so the same code handles ICML 60×36 landscape, ICLR 24×36 portrait, CVPR A0, etc. without flags.

Every gate render also serves MathJax from the skill's **bundled copy** (`assets/mathjax/tex-svg.js`, MathJax 3.2.2 — the renderer intercepts the templates' CDN request), so math typesetting during measurement is deterministic and offline-safe; a hand-opened `poster.html` still loads from the CDN as before.

## Enhanced gates & fix discipline (vendored from ARIS)

These tools and the fix discipline below are vendored from ARIS's `paper-poster-html` (MIT © 2026 wanshuiyin — see `NOTICE.md`). They layer on top of the Step 4 / Step 6 gates and reuse posterly's own `_posterly` engine. For a poster scaffolded from posterly's own templates they are the **default loop, not extras**: `run_gates.py` is the Step 4 driver and `style` is a hard gate every iteration (`asset` stays opt-in via `--manifest`). The bare `poster_check.py` core (preflight / measure / polish / verify-final) is the **fallback** only for a non-tokenized or imported template that can't pass `style` — it is *not* a license to skip `style` on a poster built from these templates.

### One-shot gate runner — `run_gates.py`

Instead of calling `measure` / `preflight` / `polish` by hand each iteration, run all gates in their load-bearing order and get the whole fix surface in one report:

```bash
# core gates (preflight + style + measure + polish); --tokens carries the
# Step 2.5 pack (design_tokens.json, always written at lock time):
python tools/run_gates.py poster.html --tokens design_tokens.json --report GATE_REPORT.json
# add --manifest to also run the real-figure asset gate (see below):
python tools/run_gates.py poster.html --tokens design_tokens.json --manifest FIGURE_MANIFEST.json --report GATE_REPORT.json
```

Order is fixed: `preflight → style → asset → measure → polish`. The cheap static gates (preflight/style/asset) run before the expensive renders (measure/polish), so a structural or style bug fails fast instead of burning a render. `GATE_REPORT.json` holds every gate's pass/fail + findings — one read tells you the whole fix surface. Child processes run with `sys.executable`, so it uses the same interpreter/venv as posterly. By default `run_gates.py` forwards `--style-disable 4,5` to the style gate (posterly's default — see **§Style HARD gate** below for what that drops and how to re-enable). Plain `poster_check.py measure` still works if you don't adopt the style/asset gates.

Without `--manifest`, the asset gate is **opt-in** — it is reported `NOT_RUN` and excluded from `overall` (real figures not verified), so a green `overall` means *the gates that ran* passed, not that figures were checked. (This is a posterly fix to the vendored orchestrator — see `NOTICE.md`; upstream silently counted the missing-manifest asset gate as a pass.)

### Style HARD gate — `style_check.py`

The Step 6 `polish` gate is *soft* (aesthetics). `style_check.py` is a **hard** gate for the design-system discipline the templates assume:

```bash
python tools/style_check.py poster.html --disable 4,5 --tokens design_tokens.json   # posterly default; the pack is always written at lock time (Step 2.5)
```

14 rules: colors only via `var(--…)` from the `:root` token block (no stray hex), no inline `style=`, no gradients, font-family against a whitelist, font-size only from the `--fs-*` scale, bounded token count, the `data-*` / inline-SVG contracts, (rule 13) every `block--modifier` variant class used in the markup must have a matching CSS rule, and (rule 14) every numeric utility class used (`w-65`, `mt-2`, `sr-46`) must have one too — an undefined width utility lets the figure render at natural size and balloon its column (three wave-2 posters hit exactly this) — a dropped rule leaves the class inert and the layout silently wrong (e.g. a `keybox--4` with no `.keybox.keybox--4` rule falls back to the 3-col base grid, orphaning a 4th tile into an empty second row). Pure static analysis plus a small Playwright render gate for computed-style rules, so it's cheap — run it right after the Step 3 scaffold and on every layout change.

**posterly default — rules 4 and 5 are disabled** (`run_gates.py` forwards `--style-disable 4,5`): rule 4 (≤2 non-neutral hue families) and rule 5 (no gradients) are *design-opinion* rules, so palette breadth and gradients are left to you. The other 12 — the *operational* discipline: token-only colors, no inline `style=`, the font/size scale, the data-attribute and variant-class contracts — stay enforced. A disabled rule still runs and shows in the report as `SKIPPED`; it just no longer drives pass/fail. Calling `style_check.py` directly enforces all 14 unless you pass `--disable 4,5`; re-enable everything with `--style-disable ''` on `run_gates.py`.

> **Note.** `style_check` assumes a *tokenized* template — a `/* ===== DESIGN TOKENS ===== */ … /* ===== END DESIGN TOKENS ===== */` block, colors via `var(--…)`, sizes via `--fs-*`, no inline `style=` / gradients. posterly's `*_neutral.html` templates **are** tokenized (vendored from ARIS — see `NOTICE.md`), so a poster scaffolded from them passes `style` out of the box. A hand-written or imported non-tokenized template will FAIL `style` until you tokenize it; the other gates (`preflight` / `measure` / `polish`) don't require tokenization.

> **Reconciling with the older layout examples.** Some examples in *Step 6 / Visual polish gates* below set figure widths with inline `style="width: …"`. `style_check` (rule 2) forbids inline `style=` **except** `style="width: NN%"` on an `img[data-source="paper"]` and anything inside a `data-color-exempt="logo"` element. So if you adopt `style_check`, express figure widths via the `w-95` / `w-100` utility classes (see `templates/COMPONENTS.md`) or a tokenized component rule rather than taking the bare inline-`style=` snippets literally — and size logos by their size class or a tokenized variant (Gate E), never a bare inline height on the slot.

### Real-figure provenance gate (optional) — `asset_check.py` + figure tools

Step 1–2 sets a ≥2× resolution *target*; this gate enforces a hard **1.5× floor** (a 2× source clears it comfortably) for the workflow where you want a guarantee that every paper figure is genuinely from the paper (not AI-fabricated, not a tiny decorative thumbnail). **Needs the `figures` extra**: `pip install -e ".[figures]"` (PyMuPDF + Pillow).

1. `python tools/extract_pdf_figures.py paper.pdf --out fig_work/ contact-sheet` → a labelled page grid to read crop bboxes off; then the `auto` (candidate regions) and/or `crop` subcommands at 300–450 DPI (the top-level `--out` goes **before** the subcommand). **A human confirms crop choices** (🚦).
2. `python tools/preprocess_figures.py fig_work/fig.png --autocrop --manifest FIGURE_MANIFEST.json` → trims white margins, checks resolution, and (with `--manifest`) re-syncs each crop's `natural_px` / `sha256` so the manifest stays honest. Without `--manifest` it autocrops but leaves stale hashes that `asset_check` will then reject.
3. Embed as `<img data-source="paper" data-asset-id="fig1">`; record each in `FIGURE_MANIFEST.json` (page, bbox, dpi, sha256, natural_px, `from_paper: true`).
4. `python tools/asset_check.py poster.html --manifest FIGURE_MANIFEST.json` → fails unless ≥2 paper figures resolve to manifest entries with matching sha256 and a rendered area **inside a band** — per-figure `≥1.5%` of the poster (floor) to `≤13%` of the body (cap), total `12–28%` of the body (warn above 24%; target ~14–22%; `--hero` raises the per-figure cap to 42% for a hero centerpiece). So a too-small figure *and* an oversized one both hard-fail — worth knowing if you enlarge figures for a Light-density poster. Theory-only papers waive the total-area rule at a human checkpoint (`--waive-total-area`), never silently.

If you don't adopt this contract, skip it — the other gates don't require `data-source` / manifest markup.

### Fix discipline — softened closed-set fix vocabulary

The failure mode of any "render → review → fix → re-render" loop is the **patch loop**: the agent fixes one nit by adding an inline style / a new hex / a one-off SVG, the next gate flags *that*, and it never converges. The discipline below keeps the Step 6 loop bounded. It is the **softened** form of ARIS's closed set — half-closed, with a smooth escape hatch — suited to posterly's human-in-the-loop use:

- **Prefer the named knobs.** Every fix inside the loop should be one of the 7 operations catalogued in `templates/COMPONENTS.md` (edit a `:root` token; swap/add/remove a catalogued component; rebalance paper-sourced content; reselect template/canvas; edit a component's token-only CSS; toggle a predefined variant; fix an asset). These are *named, reusable* knobs, not one-off hacks.
- **No one-off hacks.** No new inline `style=`, no new hex anywhere (colors come from tokens), no bespoke decorative SVG, no single-element font-size override — `style_check.py` enforces these as hard rules.
- **Escape hatch (the softening).** If a fix genuinely needs something outside the catalog — a new token, variant, or component — the agent may **propose** it explicitly, flagged as a *system extension* for your review, rather than being hard-blocked. On approval, add it to `COMPONENTS.md` / the token block and re-run from Step 3 so it passes `style` from a clean state. Don't splice a new element into a mid-loop poster silently.
- **Round caps are a guide, not a wall.** Default: ≤3 issues per round, and after ~3 rounds without reaching your visual bar, stop patching and escalate (reselect template/content, or a human call) rather than endless cosmetic micro-tuning. Adjust the caps deliberately — you're in the loop.

### Cross-model final review (strengthens Step 6.5)

Step 6.5 becomes a true **final gate** when run after `run_gates.py` is all-green and polish warnings are zero-or-waived: open a **fresh, cross-model** thread (a different model family than drafted the poster — e.g. Codex `gpt-5.6-sol`, `xhigh`) on the *final artifacts only* — `poster.html`, the rendered PDF/PNG, the paper source, and `GATE_REPORT.json` — passed as **paths, no executor framing**. It re-checks fidelity/overclaims on the *polished* text (polish introduces new claims), residue (`\ref{`, `TODO`, raw `<` in math, missing images, remote URLs), visual rhetoric (headline numbers prominent, banner readable at 2 m), design coherence (the sheet delivers its own `DESIGN DIRECTION` block — concept, single hero moment, component-native figure mounts, poster-voiced microcopy and earned emphasis; Step 6.5 item 4's restraint applies), and gate-log coherence. The reviewer *recommends*; it does not edit. Any fix loops back through Step 4/6 — never straight to re-review.

## Templates

See `templates/README.md` for the gallery. Current set (all **tokenized** — pass `style_check` as shipped):
- `landscape_4col_neutral.html` (60×36 in, 4 cols)
- `landscape_hero_neutral.html` (60×36 in, hero + supporting col)
- `portrait_2col_neutral.html` (24×36 in, 2 cols)

Adding a template: keep it neutral (no lab branding), preserve the `data-measure-role` scheme, tokenize it (DESIGN TOKENS block + `--fs-*` scale, colors via `var(--…)`, no inline `style=` / gradients) so it passes `style_check`, and document the row in `templates/README.md`.

## Key rules

- **Never invent paper numbers.** Read the `.tex` source. Bench numbers, datasets, model names — all verifiable.
- **Context discipline in the measure loop.** Never emit the whole poster.html through your output (scaffold via `cp`, edit surgically); don't re-`Read` the full file each iteration — work from `measure`'s edit-targets block (source line + anchor, then read just the surrounding block to confirm before editing). Full re-reads are for: an unfamiliar template, a cross-column re-pack, structural failures, a missing/ambiguous anchor, and the final audit.
- **Respect the circuit breaker.** `measure` exit 3 means the loop is not converging — re-pack / rescope / escalate; don't `--reset-budget` to keep grinding.
- **Card-shadow visibility is non-negotiable.** A poster looks cheap when shadows are clipped.
- **Strict alignment is non-negotiable.** Spread < 5 px or it's not done — do not report success until `measure` exits 0.
- **Preserve user-judgment decisions across sessions.** "Do not revert" notes (`✉ stays on Author X`, `α-sensitivity card removed`) — re-read the user's prior messages before "improving" a section.
