# Design axes — the composition menu

*(added 2026-07-16; distilled from a hand-picked corpus of 80 ICML 2026 posters
chosen for borrowable techniques. Numbers like `65626` are anchor poster IDs
from that corpus — re-fetch any of them at
`https://icml.cc/media/PosterPDFs/ICML%202026/<id>.png` if you need to see the
construction, compositing alpha onto white.)*

Every poster is composed by choosing **one option per axis** below, plus 0–2
devices. Axes are orthogonal: no option on one axis may silently bind another
axis (that is enforced by the clash rules at the bottom, not by bundling).
An axis choice is a **primary option plus small modifiers** — treat each axis
as a structured object, never a single mutually-exclusive enum.

`templates/THEMES.md` holds the color-bundle pool and re-theming mechanics;
`templates/COMPONENTS.md` holds per-component contracts. This file is the
menu of *what to compose*.

## Axis 1 — Layout skeleton (`base topology + span modifier + focal content`)

| base topology | notes | anchors |
|---|---|---|
| 4-column | shipped default (`landscape_4col_neutral`) | 61119, 63713 |
| 3-column | the most common skeleton in the corpus; wider equations/figures | 62396, 64164, 66740 |
| 2-column vertical flow | portrait venues (`portrait_2col_neutral`) | 63574, 66429 |
| hero panel 1.5fr+1fr | shipped (`landscape_hero_neutral`) | — |
| center stage + wings | colored/dark middle track ~45–55%, light side tracks | 60655, 64621, 65263, 67229 |
| asymmetric display-title column | title owns a full vertical track | 63136, 61403 |
| horizontal band-rows | rows, not columns; needs a side or top nav signal | 65626, 66466, 63290 |
| mosaic / named-area grid | modules span rows/cols; dashboard feel | 63300, 63640, 65372 |
| top hero + bottom grid | full-width top region, results grid below | 66579, 62378 |
| radial hub *(rare)* | central wheel + satellites; hard to balance | 67039, 63682 |

- `span modifier`: none / top-hero / full-width mid band. `focal content`: the
  hero region may hold a figure (60655), a statement (64621), a metric wall
  (62378), or the title itself (63136) — say which.
- Canvas orientation is venue metadata (an input), never a style choice.
- Ownership: this axis reserves *geometry* (e.g. a title track, a stage);
  how the title/identity is arranged inside it belongs to Axis 8.

## Axis 2 — Canvas (`base + treatment + coverage`)

- **base**: white / cream (64736, 66466, 65205) / light tint (63507, 65748) /
  brand hue (67218 sage, 60839) / near-black (65626, 66072).
- **treatment**: flat / gradient (63507, 66383) / textured-decorated *(rare;
  whole-page ornament belongs here, per-module ornament belongs to Axis 6)*
  (60839 constellation, 66372 gilt page frame).
- **coverage**: full / split two-tone (64621 white+crimson center, 65263,
  65469, 67229) / visible gutter-as-frame — cards sit edge-to-edge and the
  canvas shows only in the gutters, reading as a frame (65423 dark slate,
  67218 pale sage; the gutter color is just `base`).

## Axis 3 — Palette (`role topology + hue relationship + paint modifier`)

- **role topology**: accent-only / accent + emphasis register `--emph`
  (shipped default; pool & derivation in SKILL.md + THEMES.md) /
  dual-semantic — two hues carry two fixed meanings poster-wide (64834
  green=language vs orange=translation) / categorical multi-role (63640,
  65372, 66057; style rule 4 caps at two declared hue slots (accent/emph),
  so categorical palettes keep rule 4 disabled — posterly's default — and
  record the full palette in the poster's `DESIGN DIRECTION` block).
- **hue relationship**: distinct centers / **same-center tonal** — emphasis by
  lightness/saturation only, one hue family (63819). This is a legitimate
  choice; the emphasis register does NOT have to be hue-distinct.
- **paint modifier**: solid / gradient-as-identity on display type or arrows
  (67122, 63300) / neon — requires dark ground + luminous frame, see clash
  rule 4 (66072).

## Axis 4 — Typography (`base voice + accent convention`)

- **base voice**: LaTeX-serif paper (62587, 66740, 65107) / serif display +
  sans body (64736, 67045) / grotesque (65423, 67122, 60655) /
  rounded-playful (60472, 64049).
- **accent convention** (stackable on any voice): none / letterspaced
  small-caps eyebrows (64736, 65626, 61797) / mono accents for code, numerals,
  URLs (66427, 66466, 67122).
- Font families must be on the style-gate whitelist or declared via the
  `--tokens` `fonts:` extension; vendor any webfont locally (never a CDN).

## Axis 5 — Density & rhythm

`sparse showcase` (60655, 64621, 67122) / `balanced` (64736, 66653) /
`dense report` (60839, 62396, 65221). Drives the font-scale, padding and
gutter tokens together. This is a *capacity decision*: if content does not
fit, change topology/density or cut content — never shrink body text below
the floor (clash rule 1).

## Axis 6 — Card surface & frame (`surface × frame-line × elevation`)

- **surface**: transparent (no card; 64164, 67122) / canvas-tint (66243,
  66429 grey fills) / white / brand slab (66579, 66057) / white cards floating
  on a colored canvas (63507, 67218).
- **frame-line**: none / hairline / thin colored (65714, 66774) / thick
  colored (63300, 67045, 63713) / dashed (62901, 66383) / luminous outline
  (66072) / ornamental (66372).
- **elevation**: flat / shadow / outer glow (dark grounds only, rule 5).
- **modifiers** (compose with any frame): left-edge admonition bar (66427,
  61312) / corner type-tab "Lemma/Def/Theorem" (62998) / edge-attached
  subclaim chips riding a card edge (66057).
- **secondary/inner profile**: nested modules may declare a second frame
  profile (63640: soft outer card, dashed square inner boxes; 60839, 65372) —
  instantiate only when the design actually nests.
- Corner radius: `--rs` scales every element class proportionally (1 = shipped
  soft look, 0 = square). Per-class overrides only when a design needs
  cross-class divergence (square cards + pill chips).
- Figure mount: paper figures follow the frame decision through `--fig-bg` /
  `--fig-frame` (ground + keyline on `.figure img` / `.ff-fig img`). Restyle
  the mount together with the cards so figures sit *in* the design rather than
  pasted on it; `--fig-frame: transparent` gives a frameless mount.

## Axis 7 — Section-heading joint (`joint shape + marker + content form`)

The richest axis in the corpus, and invisible until you look for it.

- **joint shape**: plain title (63953) / underline rule (65287, 66243) /
  trailing rule to the card edge (63030, 61312) / full-width solid bar
  (61273, 63136, 64164, 67229; capsule-bar variant 63819) / floating pill
  above the card (63640) / **fieldset-legend** — the title breaks the border
  line (66774, 63030) / **ribbon-tab riding the border** — a solid capsule
  overlapping the frame's top edge, centered (62901 on a dashed frame) /
  centered title with short flanking dashes (64834, 63713) / vertical rotated
  rail (65221, 62054) / margin-detached side tabs (60472) / chevron banner
  (64618).
- **marker**: none / number chip (63757, 64736, 63574, 61894) / giant numeral
  + eyebrow (65626, 66466) / icon (60505).
- **content form**: nominal label / claim sentence as heading (66207, 67122) /
  question form (65205, 63210) / two-tier eyebrow + headline (61797, 61894).
- The three sub-choices combine freely (number chip + question form is fine).

## Axis 8 — Masthead & footer (`masthead + footer + identity accessory`)

- **masthead**: plain centered row with corner logos (62396, 65372) /
  left-aligned no band (66429, 67122) / brand color band (63030, 65423,
  62378, 65748) / title in a slab or inside the stage (60655, 63300; stage
  geometry is Axis 1's) / eyebrow + display masthead (64736) / demoted title +
  promoted question hero (66579, 67122) / project wordmark (65221, 64049,
  66466).
- **footer**: none / contact strip / manifesto band — one actionable sentence
  plus a few metrics (65205 "Front-load your dropout.", 61797, 60839) /
  sandwich — footer echoes the masthead band (63627, 64834, 64160).
- **identity accessory**: logo wall / QR-CTA component with labeled tags
  (65372 "SCAN ME", 65748) / logo+QR side rail (65626, 66579) / faint corner
  watermark (`.ornament`, shipped commented-out in the templates — the same
  corner mark on every poster is a fingerprint, so enable it deliberately).
- All three sub-choices are independent (63030 = brand band + footer strip).

## Devices pool (pick 0–2, all local & pluggable)

numbered reading path · TL;DR full-width band (63627, 63844, 66466, 65626) ·
local statement card (a full-column statement spine is Axis 1 focal, not a
device) · metric scoreboard (62378 four colored numerals, 64736, 65205,
66427) · per-section takeaway strips (66243, 67045) · question-hook opener
card (66429, 66466) · before/after pair (65524, 66072) · evidence wall
(62378, 65714) · pull quote / aphorism (65205, 67218, 67229) · QR CTA ·
mascot/sticker (64049 owl, 64618, 65221, 66372) · table winner-cell highlight
(64160) · central hub badge (63640) · steelman "alternative views" panel
(67229) · inline marker highlight on keywords/formula fragments, reusing
palette roles (61312, 63757, 67045) · edge-attached subclaim chips (66057) ·
cross-panel process connector (67218, 63844).

## Clash rules

**Hard (check, don't debate):**

1. Capacity gate: content volume × layout × density must satisfy the minimum
   font/padding floors. If it doesn't fit, change an axis or cut content;
   never shrink body text.
2. Fieldset/ribbon joints need a real border (`frame-line ≠ none`); side tabs
   need reserved margin; a vertical rail needs band-row structure and track
   width.
3. Masthead mode must match Axis-1 reserved geometry (display-title column
   masthead → layout has a title track; title-in-stage → layout has a stage).
4. Neon paint → low-luminance ground + luminous outline or glow. Never on
   white.
5. Glow/luminous effects only where the *local* background is dark (a white
   poster with one dark slab may glow inside the slab only).
6. Transparent surfaces: check ink contrast against the worst point of the
   actual backdrop (split/gradient grounds included). Imported figures on
   dark grounds need a light plate or an inverted rendition.
7. Semantic carry-through: a hue that carries a meaning keeps it poster-wide;
   categorical palettes pass distinctness + color-blind checks; a claimed
   semantic hue is never reused decoratively.
8. Attached/nested constructions: edge-attached chips and floating pills must
   not be clipped (`overflow`) or collide with the block above; a secondary
   inner frame must survive a global "borders off" choice.
9. Text on gradients/slabs: contrast computed at the worst-contrast point
   under the text, not the average color.

**Soft (legal but weigh deliberately):** shadows on dark grounds (avoid only
low-contrast grey drop shadows — outlines/glow/inner shadows fine, 66072) ·
borderless layouts need *some* alternative grouping signal (gap, rules,
heading bars, alignment — not necessarily bigger gaps) · sparse density with
4 columns · cream canvas with grotesque type · tonal palette with a metric
scoreboard.

## Recipes

The seven named recipes (宣言色板 / 纸感学术 / 暗夜编辑 / 奶油刊头 / 工程报告 /
机构单色 / 粉彩圆角) are intended as **per-axis default bundles with
compatibility notes** — starting points, not packages. The full per-axis
write-ups are not yet in this file; until they land, each name works as a
ready-made **concept statement** (SKILL.md Step 2.5) naming the world the
poster lives in — adopt the name as the concept and compose the eight axes
yourself. Once the write-ups land, swapping any single axis out of a recipe
stays normal; re-check that the new pick still serves the concept, plus the
clash rules — nothing more.

## Anti-convergence

Consecutive posters in a wave must differ on at least two of: canvas,
frame-line, section-heading joint, masthead — and must not reuse the previous
poster's concept statement. The shipped default (white · soft card · plain
headings · centered masthead) counts as one combo — do not let every poster
collapse back to it.
