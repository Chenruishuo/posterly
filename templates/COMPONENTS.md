# Component contract catalog

> **Provenance.** This catalog was authored by ARIS (skill `paper-poster-html`, MIT © 2026
> wanshuiyin) on top of posterly's own component classes, and vendored back into posterly — see
> `../NOTICE.md`. Section references of the form *DESIGN_FINAL §N* / *IMPLEMENTATION_CONVENTIONS
> §N* point to that upstream skill's design docs (**not shipped here**); in posterly the
> equivalent rules live in `SKILL.md` (the visual-review loop + fix vocabulary) and the gate
> scripts under `tools/` — treat the §refs as historical pointers, not files you can open. Any
> remaining *Phase N* wording maps to posterly's `SKILL.md` Steps: Phase 1 → Step 1.5 (content
> audit), Phase 3 → Step 3 (scaffold), Phase 5 → Step 6 (visual / polish loop), Phase 6 → Step 6.5
> (final review).

This is the **authoritative component set** for posterly. The visual-review loop and the fix
vocabulary (see `SKILL.md`) may only touch components listed here. A component that is not in
this catalog **does not exist** as far as the loop is concerned: see
[New components require a checkpoint](#new-components-require-a-human-checkpoint).

Why this file is load-bearing: the anti-pattern loop in poster authoring is "agent invents a
new visual element to fix one issue, the element brings its own hex / inline style / extra hue,
the next gate flags *that*, the agent invents another element…". Pinning the component set turns
every fix into a bounded edit (swap a known component, flip a known variant, retune a token)
instead of unbounded markup invention. COMPONENTS.md is what makes fix vocabulary item (b)
("whole-instance swap/add/delete, component set drawn from COMPONENTS.md") well-defined.

These component classes are posterly's own (© 2026 Ruishuo Chen — AGPL-3.0 as part of posterly).
The ARIS fork that wrote
this catalog only de-gradients them, tokenizes their colors/sizes, and strips inline `style=`;
class names did not change, so the catalog applies to posterly's templates directly.

---

## How to read each entry

| Field | Meaning |
|-------|---------|
| **Purpose** | The single job this component does. If your content needs a different job, you need a *different* component, not a restyled one. |
| **Allowed variants** | Predefined modifier classes only. Adding an undeclared variant = fix-vocabulary violation. |
| **Required data attributes** | Attributes a gate keys off. Omitting them breaks a gate (usually `measure` or `asset_check`). |
| **Token usage** | Which `--*` tokens the component's CSS references. Component CSS may **only** name colors via `var(--…)` (style_check rule 3). |
| **Inspected by** | Which gate(s) read this component. Tells you which gate a bad edit will trip. |
| **Allowed fix operations** | Subset of the fix-vocabulary letters `(a)–(g)` (defined in [Fix vocabulary](#fix-vocabulary) below) legal on this component. |
| **Anti-patterns** | Specific things the loop has been caught doing. Each maps to a HARD style/asset rule, a rubric cap, or (for the disabled rule 4/5 cases) the catalog convention noted above. |

Gate name shorthand (DESIGN_FINAL §3–§7):
`preflight` (structure), `style` (`style_check.py`, 13 rules), `asset` (`asset_check.py`),
`measure` (`poster_check.py measure`, column/footer/canvas geometry),
`polish` (`poster_check.py polish`, figure-AR / orphan / whitespace).

> **posterly default — style rules 4 & 5 are OFF.** posterly runs `style_check` with rules
> **4 (≤2 non-neutral hue families)** and **5 (no gradients)** disabled (`run_gates.py` forwards
> `--style-disable 4,5`) — palette breadth and gradients are the author's call. So the
> per-component "rule 4" / "rule 5" notes below describe the catalog **convention** (the templates
> ship ≤2 hue families and flat fills, and keeping them that way is the recommended default), not
> a hard failure — they only hard-fail if you re-enable them with `--style-disable ''`. The other
> 11 rules (token-only colors, no inline `style=`, the font/size scale, the data-attribute and
> variant-class contracts) stay HARD.

---

## card

- **Purpose**: The atomic content unit inside a column — holds one section's prose, list,
  figure, equation, table, or callout. Everything in the body lives in a card.
- **Allowed variants**: `.card.highlight` (accent left-bar + tinted emphasis, for the most
  important card in a column), `.card.tinted` (subtle `--bg-card-tint` fill), `.card--compact`
  (predefined tighter padding variant — fix vocabulary (f)). No other modifiers.
- **Required data attributes**: `data-measure-role="card"` (every card; `measure` aligns card
  bottoms across columns using this).
- **Token usage**: `--bg-card`, `--bg-card-tint`, `--bg-emphasis`, `--accent` (highlight
  left-bar / border-strong), `--border-soft`, `--text-primary`. Shadow uses a token-derived
  rgba allowed by style rule 5 only at alpha ≤ 0.06.
- **Inspected by**: `measure` (card-bottom spread < 5px, intercard gap 12–50 HARD), `polish`
  (CARD/TRAILING — blank below a stretched card's content; CARD/INNER-VOID — a mid-card void
  when a bottom-pinned tail stretches in an equal-height row), `preflight`
  (valid role), `style` (no inline style, colors via var).
- **Allowed fix operations**: (a) token retune, (b) move/add/delete a whole card across columns,
  (c) content rebalance inside the card, (e) global card stylesheet change (tokens only),
  (f) switch to `.card--compact` / `.card.highlight` / `.card.tinted`.
- **Anti-patterns**: inline `style="background:#…"` on a card to "make it pop" (style rule 1/2);
  padding a card with blank lines to fill column height instead of moving content (measure
  intercard-gap HARD fail / polish CARD/TRAILING, rubric "half-empty card" cap ≤5);
  bottom-pinning a card's footer with `margin-top:auto` in an equal-height row of unequal
  content (opens a mid-card void → polish CARD/INNER-VOID); a fourth highlight per column (dilutes
  the single-accent discipline, rubric ≤4 if it adds a hue family).

## numbered-card (`.card` + `.section-title` with `.num`)

- **Purpose**: A `card` whose header is a numbered section title — the standard reading order
  cue ("1 Motivation", "2 Method"…). Not a separate element: it is `.card` containing
  `<div class="section-title"><span class="num">N</span><span class="st-text">Title</span></div>`.
  **The title text — and any ★ marker — MUST sit inside the `.st-text` span.** That is what lets
  a long heading wrap as natural text with a hanging indent. Without the wrapper the round number
  badge gets stranded on its own line and the title is pushed below it, because a flex/`:has`
  fallback then floats the badge (graceful, but not the intended centred form). Do not insert a
  manual `<br>` to force a break; let `.st-text` wrap on its own.
- **Allowed variants**: inherits all `card` variants. The `.section-title` may carry a small
  inline emphasis-colored "★ KEY" / "★ Headline" marker as the **last child of `.st-text`**, glued to the
  preceding word with `&nbsp;` (e.g. `…Result&nbsp;<span class="key-mark">&#9733; KEY</span>`) so
  it can never widow onto its own line. Use the template's emphasis marker class (`.key-mark` in
  landscape_4col, `.tag-key` in portrait) — never an inline `style="color:…"`.
- **Required data attributes**: same as `card` (`data-measure-role="card"`). The number itself
  carries no data attribute.
- **Token usage**: `.section-title` → `--accent-deep` (text), `--font-sans`; `.num` →
  `--accent` background, white text. Font-size via `--fs-7` (section title) and `--fs-5` (.num).
- **Inspected by**: `measure`, `preflight`, `style` (font pairing rule 6 — section title must be
  the sans stack; rule 8 — font-size via `--fs-*`).
- **Allowed fix operations**: (a), (b), (c), (e), (f). Renumbering is content rebalance (c).
- **Anti-patterns**: section title rendered in the serif body stack (rule 6 HARD); a per-title
  font-size override in px (rule 8 HARD); decorative inline SVG icon next to the number instead
  of the `.num` circle (rule 11 HARD — no homemade decorative SVG).

## figure-card (`.card` containing `.figure`)

- **Purpose**: A card whose payload is a paper figure: `.figure > img + .caption`. The primary
  carrier of real, paper-sourced images (the thing `asset_check` exists to enforce).
- **Allowed variants**: `.figure--wide` (predefined, image spans full card width — fix (f));
  the `<img>` width is set with the utility classes `.w-45 … .w-100` (5% steps), never inline,
  **except** the one sanctioned inline exception below.
- **Required data attributes** (only when you adopt the figure-provenance gate — see `SKILL.md`
  "Real-figure provenance gate"; the core flow does **not** require them):
  - On the `<img>`: `data-source="paper"` **and** `data-asset-id="<manifest id>"`. These are a
    **pair** — `style_check` rule 10 hard-fails an `<img data-source="paper">` that lacks
    `data-asset-id`, so never add one without the other (and if you're not running the asset
    gate, add neither). When the gate runs, the asset id must exist in `FIGURE_MANIFEST.json`
    with `from_paper:true`.
  - Optional `data-fig-layout="beside-text"` on the `<img>` to opt the figure out of the
    AR-width gate when it legitimately shares its card with a meaningful text column
    (DESIGN_FINAL §10 (g) territory; polish honors it).
  - Sanctioned inline style: `data-source="paper"` `<img>` may carry **only**
    `style="width: NN%"` for aspect-ratio width tuning (B-contract exception); prefer the
    `.w-NN` utility class when the value lands on a 5% step.
- **Token usage**: `.figure img` border → `--border-soft`; `.caption` → `--text-secondary`,
  `--accent-deep` (caption `<strong>`); caption font-size `--fs-3`/`--fs-2`.
- **Inspected by**: `asset` (≥2 paper figures, per-figure area **≥1.5% of poster** floor / **≤13% of body** cap, total **12–28%**
  body [warn >24%, target ~14–22%; `--hero` raises the per-figure cap to 42%], natural_px ≥1.5×
  rendered, manifest fields + sha256 — an *oversized* figure hard-fails too), `polish` (figure AR sizing:
  FIG/WIDE / FIG/SQUARE / FIG/TALL / FIG/BROKEN), `style` (rule 10 contract attrs; rule 4
  exempts paper images from hue clustering), `measure` (card geometry).
- **Allowed fix operations**: (c) AR-bandwidth width adjust, (f) `.figure--wide`, (g) asset fix
  (re-crop, swap for a sharper figure from the *same* paper, re-run preprocess). Width changes
  via `.w-NN` utility (b/e) or the sanctioned `style="width:NN%"`.
- **Anti-patterns**: a paper `<img>` carrying neither `data-source` nor `data-asset-id` —
  invisible to asset_check, so it doesn't count toward the ≥2 quota (add both if you mean to run
  the gate); `data-source="paper"` *without* `data-asset-id` (that pair-mismatch is the rule 10
  HARD failure); a wide figure shrunk into a gray
  margin below 65% width (polish FIG/WIDE — and 65% is the defect *floor*: a figure that owns
  its card reads best at 90–100% width, field-calibrated in ResearchStudio's wave where
  70%-era floors still shipped visible small-stamp cards); a low-res crop where natural_px < 1.5× rendered
  (asset WARN→FAIL); fabricating/“illustrating” a figure not in the paper (rubric ≤3 cap,
  manifest `from_paper` must be false → fails the paper-figure quota).

## hero-figure (`.hero` + `.hero-stage` > img, `landscape_hero` template only)

- **Purpose**: The single dominant visual on the hero template — one large figure / system
  diagram / table that *is* the poster's message. Replaces the framework banner.
- **Allowed variants**: optional `.hero-caption` and one optional `.hero-aside` text block; a
  `.stage-placeholder` is shown only while authoring (must be removed once the real img drops
  in). The hero `<img>` has **no border** (the `.hero-stage` frames it).
- **Required data attributes**: `data-measure-role="hero"` on the `.hero` panel (mutually
  exclusive with `data-measure-role="banner"`). The hero `<img>` carries the same
  `data-source="paper"` + `data-asset-id` contract as any paper figure (asset_check probes the
  hero centerpiece too — the worst image to silently lose).
- **Token usage**: `--bg-card`, `--border-soft`, `--accent` (8u left-bar), `--bg-card-tint`
  (stage gradient → flattened in the ARIS fork), `--bg-emphasis` (`.hero-aside`). Section title
  font-size `calc(var(--fs-7) * …)` is a predefined hero variant (rule 8 calc exception).
- **Inspected by**: `asset` (counts as a paper figure; FIG/BROKEN on the hero img is fatal),
  `polish` (hero img BROKEN check), `measure` (hero bottom must bottom-align with the supporting
  column's last card, spread < 5px), `preflight`, `style`.
- **Allowed fix operations**: (c), (d) (switch templates if hero is the wrong frame),
  (f) hero variants, (g) asset fix.
- **Anti-patterns**: padding the hero with empty space to fill the row (rubric "large empty
  card/column" ≤5 cap; measure spread); putting a border on the hero img; leaving the
  `.stage-placeholder` in the final poster (preflight/polish residue); a hero img that is not
  paper-sourced (asset quota + rubric ≤3).

## banner-figure (`.framework-banner > figure.banner-figure`, `landscape_4col` banner only)

- **Purpose**: A method-overview figure inside the optional **framework banner** — the
  height-sized paper diagram that sits left of the banner text/stats. **Usually captionless**: the
  banner text block beside it is the figure's explanation, so a figcaption just duplicates it.
  `width:min-content` collapses the figure slot to the *image* (a captionless figure's slot IS the
  image — slack 0), and if a short caption *is* used it wraps at the image box and never sets the
  flex-item width, so the banner body keeps its room. Use this instead of hand-rolling a `.fb-fig`
  wrapper or a bare `<img class="w-100">` in the banner.
- **Allowed variants**: none. No `.w-NN` utilities (the `.framework-banner img` `width:auto` rule
  wins over `.w-NN` anyway), no inline `style=`, no ad-hoc `.fb-fig` / `.banner-img` wrapper. An
  annotated diagram-left / notes-right banner visual would be a *new* catalogued component
  (human-checkpoint), not a tweak of this one.
- **Required data attributes**: the parent `<section class="framework-banner">` keeps
  `data-measure-role="banner"`. The `<img>` carries the normal paper-figure pair
  `data-source="paper"` **and** `data-asset-id="<manifest id>"` when the asset gate runs — a pair
  (rule 10 hard-fails one without the other); add neither if the gate is off.
- **Token usage**: caption → `--font-sans`, `--fs-2`, `--text-secondary`, `--accent-deep` (caption
  `<strong>`). No color literals; any image framing references `--border-soft` / `--bg-card`.
- **Inspected by**: `style` (no inline style, tokenized caption font/color, the
  data-source/data-asset-id pair), `asset` (counts as a paper figure when manifest-backed),
  `polish` (**BANNER/IMAGE-SLOT** — fires when the figure slot is much wider than the image: a
  one-sided dead band, or a long caption stretching the slot), `measure` (indirectly, via banner
  height).
- **Allowed fix operations**: (b) add / delete / swap the whole `banner-figure`; (c) shorten or
  reword the caption from paper-sourced text, or pick a better method-overview asset; (e) global
  `banner-figure` stylesheet (tokens only); (g) asset fix (re-crop / swap for a sharper figure from
  the *same* paper).
- **Anti-patterns**: adding a figcaption that just restates the banner text block (usually
  redundant — default to no caption); a height-sized `img { width:auto }` in a shrink-to-fit flex
  item with an **unconstrained caption** (the caption's max-content width becomes the slot width —
  the BANNER/IMAGE-SLOT failure); relying on `text-align:center` to centre a **block** image (it
  doesn't — use `margin-inline:auto`); `figcaption { white-space:nowrap }`; `class="w-100"` on a
  banner image (inert — `.framework-banner img`'s `width:auto` wins); bespoke `.fb-fig` / `.fb-body`
  CSS not in this catalog.

## eqn (`.eqn`, optional `.eqn .label`)

- **Purpose**: A display-equation block — MathJax-rendered math with an optional uppercase label
  ("CORE EQUATION"). The only sanctioned home for math.
- **Allowed variants**: `.eqn--large` (predefined `font-size: calc(var(--fs-5) * 1.25)` — the
  one calc-on-token variant blessed by IMPLEMENTATION_CONVENTIONS §E.9 and style rule 8/§12.5
  nit 1). No other size variant.
- **Required data attributes**: none. (Math is found by gate via the rendered MathJax SVG, not a
  data attribute.)
- **Token usage**: `--bg-emphasis` (block fill, flat in the fork), `--accent` (3u left-bar),
  `--accent` (`.label` text), `--font-sans` (label). Block font-size `--fs-5`.
- **Inspected by**: `preflight` (bare `<` inside `$…$`, LaTeX residue), `measure`/`polish` (if the
  page intends MathJax but no `<mjx-container>` rendered — CDN block / script error — that is a
  HARD fail at render-settle), `style` (label is sans, size via `--fs-*`). **Note:** posterly has
  *no* equation-box sizing gate — an `.eqn` left mostly empty is **not** auto-caught, so size it
  by eye (the upstream ARIS `EQN/UNDERSIZED` check is not vendored here).
- **Allowed fix operations**: (a) token retune, (c) shorten/split the equation (content
  rebalance), (f) `.eqn--large` to fill an undersized box, (e) global eqn stylesheet (tokens).
- **Anti-patterns**: raw `<` inside math (preflight — MathJax parses it as an HTML tag);
  embedding the equation as a screenshot image instead of MathJax (defeats the MathJax-rendered
  check, inflates PDF, fails the "real text" expectation); a per-equation px font-size override
  (rule 8 HARD); an `.eqn` box left mostly empty (no gate catches this — check by eye).

## callout (`.callout`, variant `.callout.emph`)

- **Purpose**: An accent-filled emphasis strip for a question, theorem, or one-line takeaway —
  the "read this even if you read nothing else" line inside a card.
- **Allowed variants**: `.callout` (solid `--accent`, white text, `<strong>` in the emphasis register) and
  `.callout.emph` (solid `--emph`, `--emph-ink` text — the ARIS fork flattens the original
  gold *gradient* to a flat fill per §E.2). No third variant.
- **Required data attributes**: none.
- **Token usage**: `.callout` → `--accent` bg, white text, `--emph` (`<strong>`); `.callout.emph`
  → `--emph` bg, `--accent-deep` text. Font-size `--fs-4`.
- **Inspected by**: `style` (rule 5 — `.callout.emph` must be a flat fill, no `linear-gradient`;
  rule 4 — its accent/emph are the two allowed hue families; rule 1/3 — colors via var),
  `measure` (counts toward card height).
- **Allowed fix operations**: (a), (b) add/remove a callout instance, (c) reword from paper
  source, (f) toggle `.callout` ↔ `.callout.emph`.
- **Anti-patterns**: `linear-gradient` fill (rule 5 — convention is a flat fill; the single most
  common de-gradient regression, hard only if rule 5 is re-enabled); a third color on a callout
  (rule 4 — >2 hue clusters); using a
  callout to introduce a claim not in the paper (Step 6.5 final-HTML overclaim audit).

## result-table (`table.result-table`)

- **Purpose**: A benchmark / comparison table with the "ours" row highlighted with the emphasis tint and group
  rows / best cells marked. The quantitative payload of a results card.
- **Allowed variants**: row classes `tr.group-row` (section divider row), `tr.ours` (emphasis-tinted
  highlight for our method), cell classes `.method` (left-aligned method name), `.best`
  (accent-colored winning number). These are the defined row/cell modifiers — no others.
- **Required data attributes**: none (it lives inside a `card` which carries the measure role).
- **Token usage**: `thead th` → `--accent` bg / white; `tr.group-row td` → `--bg-emphasis`,
  `--accent-deep`, `--accent` bottom border; `tr.ours td` → `--emph-soft`; `.best` → `--accent`;
  borders → `--border-soft`. Font is the **sans** stack (tables/headers are sans per rule 6),
  size `--fs-3`/`--fs-2`.
- **Inspected by**: `style` (rule 6 — table uses sans; rule 4 — emph-soft + accent are within
  the two hue families; rule 8 — sizes via token), `measure` (height in card), `preflight`.
- **Allowed fix operations**: (a), (c) add/remove rows or edit numbers from the paper/results
  (content rebalance), (e) global table stylesheet (tokens). Switching which row is `.ours` is (c).
- **Anti-patterns**: per-cell inline `style="color:#888"` for the reference row (the posterly
  originals did this; the ARIS fork replaces with `.text-muted`) — rule 2 HARD; numbers that do
  not match the paper/results files (Step 1.5 claim→evidence audit + Step 6.5); a third highlight
  color beyond emph-soft/accent (rule 4); **a two-column `Method | Metric` table stretched to
  the card width** — it leaves a wide empty gutter and reads sparse (field-noted in
  ResearchStudio's poster wave). When the paper reports more than one metric (two datasets,
  main + ablation, Acc + F1), give the table a column per metric so it fills its width;
  fall back to two columns only when there genuinely is a single headline number, and keep
  cells terse — a dense 3-column table beats a sparse 2-column one.

## keybox (`.keybox` > `.kb-item` × N)

- **Purpose**: A compact 2–4-up strip of headline statistics ("3.2× faster", "92% acc"),
  each a big number over a small caption. The at-a-glance numeric hook. Tiles stretch to equal
  height and **vertically center** their content, so a 1-line tile's number aligns with a
  2-line neighbour's instead of sitting top-ragged (custom tile grids must do the same).
  `.kb-label` additionally reserves **two label lines** (`min-height: 2lh`) so a 1-line and a
  2-line label occupy identical height and the big numbers land at the same y across the row.
  **Contract: keep every label ≤ 2 lines** — a 3-line label exceeds the two-line reservation
  (its tile's content grows taller than its siblings') and the row reads ragged again
  (shorten the label: drop adjectives, abbreviate, `M`/`B` units).
- **Allowed variants**: 2–3 items render on the base `.keybox` (a 3-column grid). **4 items
  REQUIRE the `keybox--4` variant** (`<div class="keybox keybox--4">`, see §`keybox--4` below) to
  switch the grid to 4 columns — without it the 4th tile falls into a near-empty second row (the
  base grid is 3-col, so 4 items lay out 3+1). Whichever you use, the **item count must fill its
  rows**: never ship a keybox whose items leave a half-empty trailing row. Each item is
  `.kb-item > .kb-num + .kb-label`.
- **Required data attributes**: none.
- **Token usage**: `.kb-item` → `--bg-emphasis` bg, `--accent` top-border; `.kb-num` →
  `--accent` (`--fs-6`, sans); `.kb-label` → `--text-secondary` (`--fs-1`, sans).
- **Inspected by**: `style` (rule 6 sans, rule 8 token sizes, rule 4 single accent family,
  **rule 13** — a `keybox--4` used in the markup must have its `.keybox.keybox--4` rule in the
  stylesheet), `polish` (Gate B typography orphans — a trailing `↑ × % ↓` glyph on `.kb-num` that
  could wrap alone must carry `.nowrap`), `measure`.
- **Allowed fix operations**: (a), (b) add/remove the strip, (c) edit stats from results,
  (f) `.nowrap` on an orphan-prone number, or toggle `keybox--4` for a 4-up strip.
- **Anti-patterns**: a lone trailing glyph wrapping to its own line (polish Gate B → add
  `.nowrap`); fabricated stats (claim audit); a per-number color/size override (rules 8/4);
  **4 tiles on the base `.keybox` without `keybox--4`** — they orphan 3+1; **the `keybox--4`
  class in the HTML but its `.keybox.keybox--4` rule dropped from the stylesheet** (a dead class →
  silent fallback to 3 columns → 3+1 orphan; this is a HARD rule-13 failure).

## takeaways-strip (`.takeaways-strip`, landscape templates)

- **Purpose**: A full-width bottom strip of 3–4 one-line takeaways ("Idea / Method / Result /
  Practical") — the 60-second narrative exit. Portrait templates drop it (final card carries
  the conclusion instead). **Optional — use judgment, don't default it on.** Keep it only when
  it earns its place as a genuine exit; if the final column cards already land the conclusion,
  or the strip would just restate the body, **drop the whole block** — a redundant strip is
  worse than none.
- **Allowed variants**: title via `.ts-title` (+ `.num` circle), items via `.ts-item` >
  `.ts-key` + `.ts-text`. Item count 3–4. No other variant.
- **Required data attributes**: `data-measure-role="footer-strip"` (measure positions it between
  body and footer; footer-gap band 30–50 is measured to this strip when present).
- **Token usage**: `--bg-emphasis` (strip bg — flattened from the posterly gradient per §E.2),
  `--border-soft`, `--accent`/`--accent-deep` (title, `.num`, item left-bar, `.ts-key`),
  `--font-sans` (keys), `--font-serif` (text). Sizes `--fs-6`/`--fs-4`/`--fs-3`.
- **Inspected by**: `measure` (footer-gap band, full-width span), `style` (rule 5 — strip bg
  must be flat, rule 6 font pairing), `preflight`.
- **Allowed fix operations**: (a), (b) add/remove the whole strip, (c) reword takeaways from the
  paper, (e) global strip stylesheet (tokens).
- **Anti-patterns**: `linear-gradient` strip background (rule 5 — convention is a flat fill, the de-gradient target; hard only if rule 5 is re-enabled);
  using it on a portrait template where it competes for scarce vertical space (use the final
  conclusion card instead); inventing a takeaway not supported by the poster body (Step 6.5);
  keeping it on by default when it merely restates the body — drop the whole block instead.

## qr-block (`.qr-block` > img + `.qr-label`)

- **Purpose**: A scannable QR pointing at the paper / arXiv / code / project page, with a small
  label. Lives in the header right-block.
- **Allowed variants**: none. The img is either a **local raster** QR or, as a last-resort
  authoring placeholder, an inline SVG QR (one of the two sanctioned inline-SVG uses).
- **Required data attributes**: none for the raster QR. If the QR is the inline-SVG fallback, it
  is exempt from hue clustering (rule 4 exempts QR) but must still be a **local** asset in the
  final poster.
- **Token usage**: `--accent` (border), white background, `--accent` (`.qr-label`, sans).
- **Inspected by**: `style` (rule 4 QR exemption; rule 11 — inline SVG allowed only for
  logo / QR fallback / catalogued structural diagram), `preflight` (warns on a remote `src` — a
  remote QR-service URL hangs `measure`'s networkidle wait and link-rots; the hang then HARD-fails
  at render-settle), verify-final (file size ≤20MB — it checks page count / dimensions / size
  only, **not** remote assets).
- **Allowed fix operations**: (a) token retune (border color), (g) asset fix (regenerate the QR
  locally at ≥2× rendered px).
- **Anti-patterns**: a remote QR-service `src` (preflight warns; the networkidle hang then
  HARD-fails at render-settle, plus link rot); a homemade decorative SVG that is not actually a QR
  (rule 11); a blurry QR below 2× rendered px (no gate checks QR resolution — verify by eye).

## venue-badge (`.venue-badge`, default text identity)

- **Purpose**: The default venue identity in the header left slot — venue / year /
  "POSTER" tag as text. The default is a **text** badge; a venue logo is opt-in — place it
  *above* this text inside `.venue-badge` (see "`logo-row` + venue-badge logo" below).
  Affiliation / lab logos go in `.logo-slot` / `.logo-row`, not here.
- **Allowed variants**: `.vb-venue`, `.vb-year`, `.vb-tag` sub-lines, plus an optional venue
  logo `<img>` placed above them (the "venue-badge logo" of the `logo-row` entry below).
  Affiliation / lab logos use `.logo-slot` instead.
- **Required data attributes**: none on the text badge. A venue logo `<img>` / inline `<svg>`
  placed inside `.venue-badge` (above the text) carries `data-color-exempt="logo"` like any
  logo. (Affiliation / lab logos are the separate `.logo-slot` / `.logo-row` path — right block,
  not this badge.)
- **Token usage**: `--accent-deep` (`.vb-venue`), `--text-secondary` (`.vb-year`), `--accent`
  (`.vb-tag`), `--border-soft` (right divider), `--font-sans`. Sizes `--fs-9`/`--fs-5`/`--fs-1`.
- **Inspected by**: `style` (rule 6 sans, rule 8 token sizes, rule 1 colors as tokens),
  `measure` (header geometry), `preflight`.
- **Allowed fix operations**: (a), (c) edit venue/year text. Adding the official venue logo is
  (b): place an `<img>` (62u; portrait 46u) inside `.venue-badge`, above the text — see
  "`logo-row` + venue-badge logo" below. (Affiliation / lab logos use `.logo-slot` / `.logo-row`
  in the right block, not here.)
- **Anti-patterns**: hardcoding a venue's brand hex inline to "match their logo" (rule 1/2 HARD —
  venue color comes from the opt-in token pack, not inline hex); a *fabricated* venue seal
  instead of an official logo file (the v31 cautionary tale); an inline-SVG venue logo missing
  `data-color-exempt="logo"` (rule 1 — its color literals trip hue clustering).

## logo-slot (`.logo-slot` > img/svg, optional)

- **Purpose**: Optional lab/affiliation logo in the header right-block. The **only** place an
  off-palette color is allowed, via explicit exemption.
- **Allowed variants**: a raster `<img>` logo, or an inline `<svg>` logo. Either way the single
  `.logo-slot` logo is height-matched to the QR so the header does not grow (shipped `--logo-h`:
  85u landscape / 75u portrait). The shorter multi-logo `.logo-row` (68u / 58u) and the
  venue-badge logo (62u / 46u) are separate containers with their own heights — don't read "85u"
  as universal. **Multi-logo equal-width stack:** add `logo-stack` to the `.logo-row`
  (`<div class="logo-row logo-stack">`) to normalize the logos by **width** and stack them
  vertically (left-aligned) instead of height-matching in a row — the right choice when two **wide
  wordmarks** (AR ≳ 2, not a square seal or tall mark — equal width would blow those up) of
  different aspect ratio read unbalanced side by side (don't also apply the height-based
  `logo-wide` / `logo-tall` / `logo-square` classes). A `logo-stack` row is exempt from the
  LOGO/QR-MISMATCH gate (aligned by width, not QR height).
- **Required data attributes**: `data-color-exempt="logo"` on the logo element — tells
  `style_check` the off-palette colors inside are sanctioned. It is **load-bearing for an inline
  `<svg>` logo** (its color literals would otherwise trip rule 1, and the inline SVG itself needs
  the rule 11 allowance); a raster `<img>` logo has no color literals in the HTML, so the marker
  is convention there, not a hard gate. Keep it on either kind so the intent is explicit.
- **Token usage**: container only (`--border-soft` if framed); the logo's own colors are exempt.
- **Inspected by**: `style` (rule 1 exemption, rule 2 inline-style exemption for the logo SVG's
  internal markup, rule 11 inline-SVG allowance), `measure` (header geometry).
- **Allowed fix operations**: (b) add/remove the slot, (g) asset fix (swap logo file). Resize via
  the size class (`logo-tall` / `logo-square` / `logo-wide`) or a tokenized variant — never a bare
  inline `style=` on the slot (style rule 2 flags it; the exemption covers only the
  `data-color-exempt="logo"` element itself, not the slot wrapper).
- **Anti-patterns**: a logo *without* `data-color-exempt="logo"` (rule 1 — its colors leak into
  hue clustering, rule 4 fails); an empty `.logo-slot` left in place (adds a stray gap — delete
  the whole div instead); using the exemption to smuggle general decorative color (rule 1 intent
  — exemption is for the logo/seal only); pairing a dense institutional **lockup** (seal + two or
  three lines of institution name) with a clean two-element corporate **wordmark** at the same
  height — the bounding boxes match but the lockup's content reads tiny and crammed next to the
  bold wordmark. The affiliation text line already prints the names, so prefer each logo's
  simplest **mark/wordmark** form (not the full lockup) when it exists, or normalize equal-width
  with `logo-stack`; this optical imbalance is a **selection/layout judgment, not a gate** (the
  boxes are already balanced, so `polish` cannot see it).

## footer (`.footer`, role `footer`)

- **Purpose**: The bottom info bar — method name, venue·year, acknowledgements, code repo,
  contact. Closes the poster.
- **Allowed variants**: `.footer .repo` (accent-colored repo/contact spans). No others.
- **Required data attributes**: `data-measure-role="footer"` (measure anchors the footer gap to
  this).
- **Token usage**: `--text-muted` (body), `--accent` (`.repo`), `--accent-deep` (method name),
  `--border-soft` (top border), `--font-sans`. Size `--fs-5`.
- **Inspected by**: `measure` (footer gap to body/takeaways 30–50, full-width span), `style`
  (rule 6 sans, rule 1 colors-as-tokens), `preflight`.
- **Allowed fix operations**: (a), (c) edit footer text, (e) global footer stylesheet (tokens).
- **Anti-patterns**: inline `style="color:var(--accent-deep)"` on the method name (the posterly
  original did this — the fork uses `.text-accent-deep` / a class; rule 2 forbids inline style);
  a remote contact-tracking pixel or remote asset in the footer (verify-final); a long raw repo
  URL / email that overflows or ragged-wraps a **narrow portrait** footer — let the QR carry the
  link and print a short `github.com/org/repo` path (the row already `flex-wrap`s and `.repo`
  breaks long tokens, but a short string is the clean fix). See SKILL Layout pitfall — footer fit.

---

## Utility classes (the zero-inline-style layer)

These exist so the templates carry **no** `style=` attribute (IMPLEMENTATION_CONVENTIONS §B —
zero-tolerance). They are not "components" but the loop uses them under fix vocabulary (f). They
are catalogued here so style_check rule 2 (no inline style) has a sanctioned alternative for
every former inline use.

| Class group | Effect | Replaces former inline |
|-------------|--------|------------------------|
| `.fs-1 … .fs-9` | `font-size: var(--fs-N)` | `style="font-size: calc(N * var(--u))"` |
| `.mt-1 … .mt-6` | `margin-top: calc(N * var(--u))` | `style="margin-top: …"` |
| `.mb-1 … .mb-4` | `margin-bottom: calc(N * var(--u))` | `style="margin-bottom: …"` |
| `.w-45 … .w-100` (5% steps) | figure `<img>` width | `style="width: NN%"` |
| `.text-secondary` `.text-muted` | secondary/muted text color tokens | `style="color:#888"` |
| `.nowrap` | `white-space: nowrap` | orphan-glyph guard (polish Gate B) |
| `.text-center` | `text-align: center` | `style="text-align:center"` |

The **only** sanctioned `style=` survivors (IMPLEMENTATION_CONVENTIONS §B): the internal markup
of a `data-color-exempt="logo"` element, and `style="width: NN%"` on a `data-source="paper"`
`<img>` (AR width tuning when the value is off the 5% grid).

---

## Fix vocabulary

Inside the visual-review loop (see `SKILL.md`), **only** these operations are allowed. Every
entry above maps its "Allowed fix operations" to these letters.

| ID | Operation | Constraint |
|----|-----------|------------|
| **(a)** | Change a `:root` **token value** | Token names fixed by IMPLEMENTATION_CONVENTIONS §A; no new tokens, no new hex outside the token block. |
| **(b)** | Swap / delete / add a **whole component instance** | Component must be in this catalog. |
| **(c)** | **Content rebalance** | Move a card across columns; add/remove paper-sourced text; adjust a figure width within the AR gate's band. |
| **(d)** | **Canvas / template reselect** | The upgrade path — pick a different template or retarget the canvas (`templates/README.md` "Picking a template"; `SKILL.md` Step 3 and Step 4 "reselect a smaller canvas"). |
| **(e)** | Global **component stylesheet** change | May reference tokens only; **no new hex**. |
| **(f)** | Toggle a **predefined variant** | `.figure--wide`, `.card--compact`, `.eqn--large`, `.nowrap`, `.callout.emph`, etc. — must already be in this catalog. |
| **(g)** | **Asset fix** | Re-crop, swap for a sharper figure from the *same* paper, re-run `preprocess_figures.py`. |

**Forbidden inside the loop** (DESIGN_FINAL §10, last paragraph): new inline `style=`,
new hex literal, homemade decorative SVG, single-element font-size override.

---

## New components require a human checkpoint

If a fix genuinely needs a component that is **not** in this catalog, the loop **must stop**.
A new component cannot be born inside the Step 6 visual loop.

The procedure (DESIGN_FINAL §10, final paragraph):

1. **Stop** the visual loop. Do not improvise the element inline.
2. **Human checkpoint (🚦)** — get explicit human approval for the new component.
3. **Add a catalog entry** here in COMPONENTS.md with all seven fields (purpose / variants /
   data attributes / token usage / inspected-by / allowed fix ops / anti-patterns), and add its
   tokenized CSS to the template stylesheet (colors via `var(--…)` only, sizes via `--fs-*`).
4. **Re-run from Step 3** (scaffold + token patch), so the new component passes `preflight` +
   `style` from a clean state before re-entering the layout/visual loop. You may not splice a
   new component into a mid-loop poster and keep going.

This is what keeps the fix loop bounded: the component set is closed during the loop, and only
a human-gated, catalogued, re-run-from-Phase-3 step can extend it.

**Known-rejected shape — the "bento" feature grid (do not propose it).** One big feature tile
spanning two rows on the left + two small cells stacked on the right. ResearchStudio's
paper2poster shipped this as a content pattern and formally retired it after a live wave:
whenever the two small cells fill with real content they grow tall, the big tile stays at its
own content height, and the tall left column ends visibly half-empty — a structurally
unbalanced look no amount of filling fixes. For paired/contrast content use side-by-side
equal cells or a highlight table; for a feature-plus-supporting shape use `keybox` /
`takeaways-strip`. If a future poster genuinely wants a bento, it still has to come through
this checkpoint — with an equal-cell fallback story.

---

## Density components (added 2026-06-05, codex-converged; user-checkpointed)

> **Shared guardrail (all components below): no component-local color semantics.**
> Semantic distinction must be conveyed by labels, order, typography, and FACT/DERIVED
> text — never by new hues. Every CSS declaration references `--accent`/`--emph`/neutral
> tokens only. This is what keeps a dense poster from regressing into the 30-color
> "patched dashboard" failure class.

### `equation-stack`
- **Purpose**: 2–4 compact formula rows (e.g. population objective + empirical loss) —
  denser than stacking full-margin `.eqn` blocks.
- **Variants**: none. **Data attributes**: none.
- **Tokens**: inherits `.eqn` tokens; tightened margins/padding only.
- **Inspected by**: style (rule 8 via `.eqn`), measure (height + the MathJax-rendered check).
- **Allowed fix ops**: rebalance (move rows between stack and prose); variant via `.eqn--large` on one row.
- **Anti-patterns**: >4 rows (split into two cards); mixing unrelated equations.

### `eqn-anatomy` (+ `eqn-anatomy--row`)
- **Purpose**: term-by-term anatomy of ONE displayed equation: each `.ea-item` = a pill
  `.ea-tag` (term name) + one-line explanation. 2×2 grid default; `--row` = 1×4.
- **Tokens**: accent family only (tint bg, accent left bar, accent-light tag).
- **Inspected by**: style rule 4 (all tags accent), measure.
- **Allowed fix ops**: token edits; 2×2 ↔ 1×4 variant swap; rebalance text.
- **Anti-patterns**: per-term colors (DPO=blue, δ=green, λ=red is FORBIDDEN); anatomy of
  an equation not displayed on the poster; >4 items.

### `flow-strip`
- **Purpose**: horizontal labeled pipeline (`.step` boxes + `.arrow` glyphs) grounded in
  paper variables, e.g. data pair → implicit reward → shift → penalty → optimum.
- **Variants**: `.step--final` (emph top bar + emph-soft bg) — at most ONE, the endpoint.
- **Tokens**: every step the same accent-light; final step emph-soft.
- **Inspected by**: style rule 4, measure, polish FLEX-BR (no `<br>` in steps — use
  `.step-name` block + text).
- **Allowed fix ops**: step count/text rebalance; token edits.
- **Anti-patterns**: calling it an "Algorithm" when the paper has none (label it
  "Objective flow" / "Loss anatomy"); per-step colors; >6 steps.

### `figure--duo`
- **Purpose**: two sibling paper figures sharing one card and ONE caption (e.g.
  failure-geometry → fix-geometry on the same axes).
- **Contract**: both `<img>` carry `data-source="paper"` + `data-asset-id` + `.w-45`/`.w-50`
  (each 42–48% of the card); combined target 8–12% of body.
- **Inspected by**: asset (provenance + per-figure + total bands), polish FIG gates.
- **Allowed fix ops**: asset fixes (re-crop), width within band, swap member figures.
- **Anti-patterns**: pairing unrelated figures; before/after labels in extra hues (use
  text labels with accent/emph only).

### `result-table` derived column (`th.derived` / `td.derived`)
- **Purpose**: a DERIVED arithmetic column (e.g. Δ = Ours − Baseline) next to verbatim
  paper values; emph-soft background marks "derived, not copied".
- **Contract**: the table caption or setup line MUST state the derivation ("Δ = AuxDPO −
  DPO, derived"). Negative/degrading values use *italic*, never red.
- **Inspected by**: style rule 4 (emph family), content audits (Step 1.5 / 6.5 verify arithmetic).
- **Anti-patterns**: mixing derived and verbatim values in one column; unlabeled derived data.

### `keybox--4`
The 4-column variant of **keybox** — see **§keybox** above for the full contract (purpose,
tokens, inspected-by, fix ops). It switches the base 3-col grid to 4 columns for a 4-up
stat/property strip (params / complexity / loss type / guarantee). The
`.keybox.keybox--4 { grid-template-columns: repeat(4, 1fr) }` rule MUST exist in the stylesheet,
or the class is inert and the 4-tile strip orphans 3+1 (`style` rule 13 hard-fails).
- **Density-specific anti-pattern**: tiles that restate the banner's headline stats verbatim —
  the strip should add *new* at-a-glance numbers, not echo the banner.

### `algo`
- **Purpose**: compact numbered procedure list — **only when the paper itself states an
  explicit algorithm/procedure**. Cite it ("Alg. 1", "the procedure of §4.2").
- **Inspected by**: `style` (token colors, font/size scale), `measure` (aligns as a card),
  content audits (Step 1.5 / 6.5 — the steps must be the paper's, not fabricated).
- **Allowed fix ops**: token edits; step-text rebalance; drop the component if the paper has
  no explicit algorithm to cite.
- **Anti-patterns**: INVENTING steps from prose (the v31 poster fabricated a "5 steps per
  batch" algorithm that was not in the paper — this is the cautionary tale).

### `claim-pills`
- **Purpose**: provenance mini-table (`.cp-id` pill + evidence + `.cp-fact`/`.cp-derived`
  badge) for numeric-heavy posters where every number should trace to a source.
- **Contract**: use only when the poster carries ≥8 distinct numeric claims; badges are
  text (FACT/DERIVED), accent/emph colored — no new hues.
- **Anti-patterns**: pills for trivial claims; turning it into a second results table.

### `logo-row` + venue-badge logo (added 2026-06-05, user-checkpointed)
- **Purpose**: institution logos in the header right block (beside the QR), and the
  official venue logo above the venue-badge text. Sized to pair with the QR
  (logo-row 68u, venue logo 62u; portrait 58u / 46u) — visible from poster distance, never tiny.
- **Contract**: REAL logo files only (user-provided or official sources) — fabricating
  a seal as inline SVG is forbidden (the v31 cautionary tale). Every logo `<img>` should
  carry `data-color-exempt="logo"` (palette-gate exemption — load-bearing for an inline-SVG
  logo, convention for a raster one) and a meaningful `alt`.
- **Tokens**: layout-only CSS; logo artwork colors are exempt by contract.
- **Inspected by**: preflight (file exists); for an inline-SVG logo, style rules 1/11
  (color exemption + inline-SVG allowance).
- **Allowed fix ops**: swap logo file, adjust the row's height token, drop a logo.
- **Anti-patterns**: fabricated/approximated seals; logos so small they read as dirt
  (< ~40u); using the logo row to smuggle decorative graphics.

### `logo-pack` — advisor-generated multi-row logo packing (added 2026-07-15)
- **Purpose**: the markup+CSS shape that `poster_check.py fit-logos` proposes when ≥3
  institution marks of mixed AR pack better in rows than in one `logo-row`: a
  flex-column wrapper of `logo-row`s, every mark still inside a `.logo-slot` (so Gate E
  keeps seeing it), heights set by ONE shared CSS rule (uniform height — marks enlarge
  together). Emitted in `var(--u)` units when the template defines `--u`.
- **Contract**: same as `logo-row` above (real files, `data-color-exempt="logo"`,
  meaningful `alt`); the advisor's snippet is a *starting proposal* — the optical-weight
  judgment (lockup vs wordmark) stays with the author, and the tool never edits the file.
- **Tokens**: layout-only CSS; the height/gap rules ride `var(--u)`.
- **Inspected by**: Gate E via the preserved `.logo-slot` wrappers (`<img>` marks only —
  an inline-SVG mark is not gated; verify by eye); style rule 2 satisfied by construction
  (no inline styles).
- **Allowed fix ops**: re-run `fit-logos` after logo changes, cap the shared height near
  the QR, demote a too-wide wordmark to a width-normalized `logo-stack` (its own row
  does not shrink it — the uniform height only grows when a row empties).
- **Re-run idempotency (`data-lf-h0`)**: when applying the snippet into a **content-sized**
  zone, also stamp the zone element with its pre-application height,
  `data-lf-h0="<px>"` (the CLI prints the exact stamp line). An applied pack collapses
  such a zone to the packed height; without the stamp a re-run measures only the
  shrunken strip and can only propose smaller. The advisor reads the stamp back as
  `max(stamp, live box)` — a template-grown zone still wins — and WARNs when it finds
  an applied pack with no stamp.
- **Anti-patterns**: pasting the snippet without the optical-weight check; keeping the
  zone's OLD logo children alongside the pack, or hand-wrapping the pack in yet another
  `logo-row` (the snippet *replaces* the zone's inner content — when the discovered zone
  is itself a `.logo-row`, `.logo-row > .logo-pack > .logo-row` is the expected shape);
  re-introducing inline `style=` to tweak one mark; re-running the advisor against an
  applied, unstamped pack and trusting the shrunken proposal.

### `vrail` — vertical-rail title (a content-agnostic band modifier) (added 2026-06-16, user-checkpointed)
- **Purpose**: a layout *modifier* for a **wide, short, full-width band** that moves the band's
  title into a **narrow left rail** — its words **stack one per horizontal line** (every word
  reads normally, NOT rotated) — so the band's **body reclaims the height** a horizontal title row
  would eat. Content-agnostic: the body it frees can be a figure gallery (`gallery-strip` below,
  the common case) or any other wide-short band you author whose content earns the freed height —
  a metrics row, say. **Not a standalone component** — you add `vrail` to a band you already have.
- **Contract** (how to make any band vrail-able): give the band's title block the class
  `.rail-title` with its text in `.rail-title-text`, and the body the title frees the class
  `.rail-body`. Add `vrail` to the `<section>` to switch on the rail layout; drop it to fall back
  to the band's own (horizontal-title) layout — the same markup serves both. If the band sets its
  own container layout for base mode — anything that positions title-vs-body (`flex-direction` /
  `flex-wrap` / `align-items` / `gap`) — scope it to `.band:not(.vrail)`, keeping only the chrome
  (bg / border / padding) and `display: flex` on the always-on `.band`. Otherwise those base rules
  tie `vrail`'s single-class row layout at equal specificity and win or lose by paste order (e.g. a
  base `flex-direction: column` would keep the rail from going to the left). See how `gallery-strip`
  below splits its rule.
- **Required data attributes**: mark the rail title `data-vrail-title` so its deliberately narrow
  stacked lines (and any agent-chosen soft-hyphen break) are **exempt from `polish`'s WIDOW
  check** — they are intentional, not runts. The gate checks the attribute on the element it
  *scans*, so put it on whichever rail element carries a WIDOW-checked prose class
  (`.section-title`, `.callout`, …), not only on a child span. (In the `gallery-strip` example the
  rail title text is not a prose class, so there the attribute is just belt-and-suspenders.) See
  SKILL.md Gate B.
- **Use ONLY on a wide, short, full-width strip** — never on a narrow column card, where the rail
  eats the scarce horizontal width and the body gets tighter, not taller.
- **Vertical-rail title rules (the craft)**:
  - Every word stays **horizontal and upright** — the rail is a *narrow column of text*, NOT
    rotated/sideways text. Size the rail width to roughly the **longest word** so the title's
    words wrap **one per line**; `text-align: center` so they stack symmetrically (this also evens
    out uneven word lengths). Any number badge (`.num` circle) sits **upright at the top** of the
    rail.
  - **An over-long word that won't fit the rail width is broken with a soft hyphen** `&shy;`
    (`Synchro&shy;nization`), placed at a sensible syllable boundary **you (the agent) judge** —
    where to break is an authoring call, so pick a clean break and never strand a single letter.
    Do **not** rely on `hyphens: auto`: the headless Chromium that renders the gate and the final
    PDF has no hyphenation dictionary, so `auto` silently no-ops and the word overflows the rail.
  - Keep the rail title **short** (≤ ~3 words). A long subtitle does **not** go in the rail — put
    it as a small horizontal caption under the body, or drop it. If a title is so long it needs
    several hyphenated breaks to fit, that is the signal to **shorten it or keep the title
    horizontal**, not to cram it into the rail.
- **Anti-patterns**: `vrail` on a narrow column card (eats horizontal width); **rotating /
  sidewaysing the title text** (`writing-mode: vertical-rl` or upright-stacked letters — the words
  must read normally); relying on `hyphens: auto` (no-ops in the headless renderer → the word
  overflows); a hyphen break that strands a single letter; a long title / long subtitle crammed
  into the rail.
- **Recipe** (the modifier — drop it on any wide-short band; the band styles its own
  `.rail-title` / `.rail-body`, `vrail` only re-lays-them-out):
  ```css
  /* vrail: title -> narrow left rail (words stack one per HORIZONTAL line); the band
     body takes the full height. Content-agnostic — keys off .rail-* roles only. */
  .vrail { display: flex; flex-wrap: nowrap; align-items: stretch; gap: calc(8*var(--u)); }
  .vrail .rail-title { display: flex; flex: 0 0 auto; flex-direction: column;
    align-items: center; justify-content: center;
    width: calc(46*var(--u)); }   /* ~ the longest word -> words wrap one per line; tune per title */
  .vrail .rail-title-text {
    display: block; width: 100%; text-align: center; line-height: 1.15; }
    /* words read normally (no rotation); break an over-long word with &shy; in the markup */
  .vrail .rail-body { flex: 1 1 auto; }   /* body fills the row beside the rail (no top title row
                                             eating height above); body lays out its own content */
  ```
  ```html
  <section class="<band> vrail" data-measure-role="footer-strip">
    <!-- data-vrail-title opts the narrow stacked title out of the WIDOW check; an
         over-long word breaks with a soft hyphen (&shy;) at an agent-judged point. -->
    <div class="rail-title">
      <span class="num">&#9632;</span>   <!-- optional badge; styled by your band -->
      <span class="rail-title-text" data-vrail-title>Synchro&shy;nization Results</span>
    </div>
    <div class="rail-body"><!-- the band's content, e.g. a gallery-strip figure row --></div>
  </section>
  <!-- a long subtitle (if kept) goes here as a small horizontal caption, NOT in the rail -->
  ```

### `gallery-strip` (added 2026-06-16, user-checkpointed)
- **Purpose**: a full-width bottom strip showing a *row of small task / example thumbnails* —
  environment thumbnails / qualitative samples / a "benchmark suite" gallery — the at-a-glance
  "what this was tested on" exit. Distinct from **takeaways-strip** (text takeaways) and
  **figure-card** (one *quota* paper figure inside a column). Optional; use only when a row of
  small example images genuinely earns the bottom band.
- **Reclaiming title-row height**: to give the figures the height a horizontal title row would
  eat, add the **`vrail`** modifier (above) to the section — the figures then fill one un-wrapping
  row and **enlarge** (~52u vs the 33u base). The rail mechanics and craft rules live in the
  `vrail` entry; here it is just a toggle.
- **Required data attributes**: `data-measure-role="footer-strip"` on the section; each `<img>`
  carries a meaningful `alt`. The thumbnails are **decorative task / environment identifiers, NOT
  quota paper figures** — so they carry **no `data-source` / `data-asset-id`** and stay invisible
  to the `asset` gate. Do **not** mark them `data-source="paper"` to make them "count": a thumbnail
  this small can never satisfy the per-figure area floor (an env icon renders at ~0.25% of the
  poster, a frame strip ~0.88% — both far under the **1.5%-of-poster floor**, which hard-fails each
  one). Marking eight of them also pushes total paper-image area past the **24% warn line** (~27%) —
  but that is only a soft warning; the hard PASS→FAIL flip is the per-thumbnail floor failures, not
  the total. A genuine result/method figure that *should* count belongs in a **figure-card**, not here.
- **Token usage**: `--bg-emphasis` (flat strip bg, de-gradient per rule 5), `--border-soft`
  (border + image frame), `--accent` (left bar + `.num` circle), `--accent-deep` (title),
  `--font-sans` (title + labels), `--text-secondary` (labels / optional subtitle). Sizes
  `--fs-6` (title) / `--fs-1` (labels).
- **Inspected by**: `measure` (footer-gap band, full-width span), `style` (rule 5 flat bg, rule 6
  fonts), `preflight` (local `src` exists; remote `src` warns). **Not** inspected by `asset` (no
  `data-source` → invisible to the provenance + area gate) and **not** size-checked by `polish` —
  its FIG/* aspect scan only walks `card` / `hero` images (banner images have a separate
  BANNER/IMAGE-SLOT check), so a `footer-strip` thumbnail is outside both paths and is bounded only
  by the recipe's own `gs-item img` height (33u, or 52u under `vrail`). Keep that height.
- **Allowed fix ops**: (b) add/remove the whole strip, swap / re-crop a thumbnail, toggle
  `vrail`, rebalance figure count / height, edit labels.
- **Anti-patterns**: a `linear-gradient` strip bg (rule 5); **marking the thumbnails
  `data-source="paper"`** (they hard-fail the asset area floor and flip the gate to FAIL — see
  *Required data attributes*); **smuggling a large result/method figure into a `gallery-strip`** —
  no gate bounds these images (`asset` can't see them, `polish` FIG/* skips `footer-strip`), so a
  full-size figure here escapes the area + provenance checks it owes: keep them thumbnails and put
  any countable figure in a **figure-card**; inventing example images the work does not contain —
  since `asset` no longer guards these, that honesty is **on you (the agent)**: use only genuine
  task / environment images from the paper, never fabricated or stock art.
- **Recipe** (the strip is not shipped in the templates — copy and adapt, as you would author any
  footer-strip; all colors via tokens; pair with the `vrail` modifier above for the rail title):
  ```css
  .gallery-strip {                       /* always: flex strip of [title | figures] + chrome */
    display: flex; justify-content: center; background: var(--bg-emphasis);
    border: calc(1*var(--u)) solid var(--border-soft);
    border-left: calc(6*var(--u)) solid var(--accent);
    border-radius: calc(5*var(--u)); padding: calc(5*var(--u)) calc(12*var(--u));
  }
  /* base-only container layout (title on its own top row, figures wrap below). Scoped
     :not(.vrail) so the vrail modifier's row layout (nowrap/stretch/gap) always wins,
     whatever order the two recipes are pasted in. */
  .gallery-strip:not(.vrail) { flex-wrap: wrap; align-items: flex-end;
    gap: calc(3*var(--u)) calc(7*var(--u)); }
  .gallery-strip .rail-title { display: flex; align-items: center; gap: calc(6*var(--u));
    font-family: var(--font-sans); font-weight: 800; font-size: var(--fs-6); color: var(--accent-deep); }
  .gallery-strip .rail-title .num { display: inline-flex; align-items: center; justify-content: center;
    width: calc(22*var(--u)); height: calc(22*var(--u)); border-radius: 50%;
    background: var(--accent); color: white; font-size: var(--fs-5); font-weight: 700; }
  .gallery-strip .gs-figs { display: flex; flex-wrap: wrap; align-items: flex-end;
    justify-content: center; gap: calc(3*var(--u)) calc(7*var(--u)); }
  .gallery-strip .gs-item { display: flex; flex-direction: column; align-items: center; gap: calc(1.5*var(--u)); }
  .gallery-strip .gs-item img { height: calc(33*var(--u)); width: auto; border-radius: calc(2*var(--u));
    border: calc(1*var(--u)) solid var(--border-soft); background: var(--bg-card); }
  .gallery-strip .gs-label { font-family: var(--font-sans); font-size: var(--fs-1);
    color: var(--text-secondary); text-align: center; line-height: 1.1; }
  /* base mode: title on its own top row */
  .gallery-strip:not(.vrail) .rail-title { flex: 0 0 100%; }
  /* + vrail (the modifier above): figures fill one un-wrapping row and enlarge */
  .gallery-strip.vrail .gs-figs { flex-wrap: nowrap; }
  .gallery-strip.vrail .gs-item img { height: calc(52*var(--u)); }   /* enlarged vs the 33u base */
  ```
  ```html
  <section class="gallery-strip vrail" data-measure-role="footer-strip">
    <!-- `vrail` (the modifier above) puts the title in the left rail; data-vrail-title
         opts the narrow stacked title out of the WIDOW check. Drop `vrail` for a
         horizontal title row. -->
    <div class="rail-title">
      <span class="num">&#9632;</span>
      <span class="rail-title-text" data-vrail-title>Synchro&shy;nization Results</span>
    </div>
    <div class="gs-figs rail-body">
      <figure class="gs-item"><img src="images/ant.png" alt="Ant environment"><figcaption class="gs-label">Ant</figcaption></figure>
      <!-- … more .gs-item figures … -->
    </div>
  </section>
  <!-- a long subtitle (if kept) goes here as a small horizontal caption, NOT in the rail -->
  ```
