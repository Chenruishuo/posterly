# Theme reference — accent bundles & re-theming mechanisms

*(added 2026-07-15; conclusions ported from ResearchStudio paper2poster's
`apply_theme.py` after its live poster wave — mechanisms re-stated for
posterly's token system, palette values carried over as a starting pool.)*

posterly templates already centralize every chrome color in the `:root`
token block, so a re-theme is mostly a **token swap**: rewrite
`--accent` / `--accent-deep` / `--accent-light` / `--accent-soft` (and
check `--accent-ink`, Mechanism 3) — plus the `--emph`/`--emph-soft`/
`--emph-ink` register triple (Mechanism 1). This file records the three
mechanisms worth keeping as the design-axes work lands, plus a
field-tested accent pool.

## Mechanism 1 — the result register stays FIXED across themes

Their `--callout` (a crimson "this is the number" cue) is deliberately **not**
swapped by any theme; posterly's analog is **`--emph` / `--emph-soft`** (the
`.ours` row, `★` callouts, `.keyword-emph`). Keep it constant when re-theming:
the reader's "result highlight" association survives across a wave of posters
(the *hue-distinction* side of that promise is what the clash resolution below
exists to protect — see the mixed-wave trade-off). **SKILL.md's clash rule
still wins** ([Palette derivation](#palette-derivation): a *warm* accent — red/orange/yellow, so the
burgundy/rust/plum rows below — requires swapping the secondary to a deep cool
neutral, e.g. `#3D4A5C`, with `--emph-soft` re-derived as its ~90% white
tint). For a **single-hue-family wave** resolve the register per SKILL.md
first, then hold that choice fixed. For a **mixed warm/cool wave** (the hash
pick below will happily land blue AND rust in one batch) the two rules can't
both be satisfied per-poster — so decide the register for the *whole batch
up front*: a deep cool neutral keeps ink readable on every accent, **but it
reads close to the slate/mono/blue accents, trading away the register's hue
distinction there — a known cost of a mixed wave, accept it deliberately**;
or constrain the wave to one hue family if you want gold.
The invariant is "the result register does not churn within a wave", not
"the register is always gold" — which is also how this coexists with the
theme-pack de-fingerprinting note ("gold demoted to optional").

**Caveat — the two register⇄accent pairings still need a contrast check.**
The templates pair the two families in BOTH directions:
`.callout.emph { background: var(--emph); color: var(--emph-ink) }`
(register as ground) and `.callout strong { color: var(--emph) }` on an
accent-colored band (register as ink on accent ground). The Phase-1
decoupling routed the first direction through **`--emph-ink`** (default
`#14314A` — 5.58:1 on the default gold `#C9A24A`; the earlier default
`var(--accent-deep)` = `#1F4566` measured only 4.16:1, below this
mechanism's own 4.5:1 bar), so a register swap is now: set `--emph`,
re-derive `--emph-soft` (~90% white tint), and re-check `--emph-ink` at
4.5:1 on the new fill (a deep cool register usually wants a light ink
instead of a dark one — dark-on-dark reads ~1.0–1.6:1). The second
direction has no token of its own: after any swap, eyeball `--emph`-as-ink
on the accent band once (Mechanism 3's `ink()` math applies).

## Mechanism 2 — deterministic seed pick, never "model picks a color"

Selecting a "random" theme via the model defaults to the same 1–2 choices in
headless runs. Pick by hash instead — reproducible spread across a batch, no
flakiness:

```python
import hashlib
def pick(options: list[str], seed: str) -> str:
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    return sorted(options)[h % len(options)]   # seed = output path
```

## Mechanism 3 — luminance-adaptive ink on the accent (WCAG)

Any text painted ON the accent (venue badge, header chip, accent pill) must
not hard-code white: a pale custom accent would wash it out. Compute the WCAG
contrast of BOTH candidate inks against the accent, pick the higher, and
verify it clears **4.5:1** (a plain luminance threshold — upstream used
`L < 0.4 → white` — picks the *wrong* ink in the mid-luminance band: on
`#808080` white gives only 3.95:1 while near-black gives 4.66:1). Store the
result as a token (e.g. `--accent-ink`):

```python
def ink(accent_hex: str) -> str:
    h = accent_hex.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    L = 0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b)
    c_white = (1.0 + 0.05) / (L + 0.05)     # contrast vs #ffffff (L=1.0)
    c_dark = (L + 0.05) / (0.007 + 0.05)    # contrast vs #141414 (L~=0.007)
    best, ratio = (("#ffffff", c_white) if c_white >= c_dark
                   else ("#141414", c_dark))
    if ratio < 4.5:
        raise ValueError(f"no AA ink on {accent_hex}; mute the accent")
    return best
```

Constraint on the pool itself: every accent dark + saturated enough that
white-on-accent clears **4.5:1** AND the accent still reads as a distinct
`h2`/border color on white cards. **Wired in Phase 1**: the templates
define `--accent-ink` (default `#FFFFFF`) and every ink-on-accent chrome
spot (chips, callout body, table heads, banner labels) references it — a
*custom* pale accent just recomputes the token with the `ink()` snippet
above instead of hunting literals.

## Field-tested accent pool (9 bundles)

`accent` + `accent-soft` are carried verbatim from the gallery-calibrated
pool; posterly needs two more tokens per bundle — derive `--accent-deep`
(darken the accent ~25%, for gradients-free depth) and `--accent-light`
(a paler tint than `-soft`, for `--bg-emphasis`) at adoption time, checking
contrast per Mechanism 3.

| name | `--accent` | `--accent-soft` | register |
|---|---|---|---|
| blue | `#1d3a87` | `#e8edf7` | classic deep-academic |
| teal | `#0f6070` | `#e2eff1` | cool, low-saturation |
| green | `#2d5f3e` | `#e6f0ea` | forest |
| burgundy | `#8f2437` | `#f6e7ea` | warm dark red |
| purple | `#4b2e83` | `#ece7f4` | deep violet |
| rust | `#a2521c` | `#f6ece1` | warm earth |
| slate | `#33415e` | `#e9ecf3` | near-neutral blue-grey |
| plum | `#7d2860` | `#f4e6ef` | magenta-dark |
| mono | `#34373b` | `#eeeff1` | grayscale "clean white" |

posterly's shipped neutral (`#2D5F8B` steel blue) stays the template default;
this pool is the *randomize-across-a-wave* menu, not a replacement. The
structure/typography axes of the theme packs live in the roadmap, not here —
this file is the color axis only.


---

## Palette derivation moved from SKILL.md

This section was relocated from the original SKILL.md and includes approved revisions. Read it when selecting/adjusting the palette; its seed-independent rules still apply when the user supplies the colors. Markdown links are relative to this file; command and inline paths remain relative to the skill root or the poster working directory, as appropriate. This relocation neither changes the earlier theme mechanisms nor resolves their pre-existing wording differences with the derivation.

<a id="palette-derivation"></a>

<!-- preserved-source: SKILL.md lines 71-135 -->
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
from PIL import Image, ImageColor

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
#    GUIDELINE: set `seed` to the official hex (e.g. "#660874") and
#    skip only the image-extraction block, not the normalization below.
im = Image.open("images/lab-logo.png").convert("RGBA")
im.thumbnail((128, 128))
px = [(r, g, b) for r, g, b, a in im.getdata() if a > 128]
cands = Counter((r // 32, g // 32, b // 32) for r, g, b in px
                if max(r, g, b) - min(r, g, b) > 40       # saturated enough
                and 60 < (r + g + b) / 3 < 200)           # mid-tone
seed = (tuple(v * 32 + 16 for v in cands.most_common(1)[0][0])
        if cands else None)  # None = this image has no usable seed --
                             # try the next signal source, neutral only last

# Stop this calculation if the image has no usable color; try another
# signal source before using the neutral palette as the last resort.
if seed is None:
    raise SystemExit("No usable seed: try another signal source; neutral only last.")
if isinstance(seed, str):
    seed = ImageColor.getrgb(seed)  # official hex -> numeric RGB tuple

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
- **Emphasis register (`--emph`) is a per-poster choice, not a fixture**: it is the single "ours / best" cue (the `.ours` row, `★` callouts, `.keyword-emph`), and defaulting it to the same color on every poster is a recognizable fingerprint. Pick ONE register per poster from a shortlist that suits the accent — warm gold `#C9A24A` (classic against cool accents), deep cool slate `#3D4A5C` (safe on any accent), rust `#A2521C`, forest `#2D5F3E`, burgundy `#8F2437` (see `templates/THEMES.md` for the calibrated pool) — and vary the choice across posters. Constraints: (a) hue-distinct from the accent (style rule 4 limits the palette to these two hue families only when enabled; ignore that limit when disabled); (b) if the accent is warm (red/orange/yellow), the register must be cool; (c) re-derive `--emph-soft` as the register's ~90% white tint and keep `--emph-ink` at 4.5:1 on the register fill. (These constraints govern the default accent+emph role topology — a deliberately different Axis 3 choice made in Step 2.5, e.g. same-center tonal or categorical roles, follows [DESIGN-AXES](DESIGN-AXES.md) instead.)
- **Backgrounds default to near-white** (`--bg-page`/`--bg-card` untouched, or at most a faint seed-hued tint) — this recipe derives the *accent* tokens, not the ground. A non-white canvas (cream / light tint / brand hue / near-black) is a legitimate **Axis 2** choice made in Step 2.5, with its own contrast obligations ([DESIGN-AXES clash rules 6 and 9](DESIGN-AXES.md#clash-rules)) and, for dark grounds, the `"dark_ground": true` declaration in the `--tokens` JSON (Step 2.5 item 4).
- **Echo the choice**: state the seed source and final tokens to the user (they surface visually in the Step 2.5 thumbnails) and record them in the Step 2.5 `DESIGN DIRECTION` comment block — "accent #660874 from Tsinghua brand; register slate #3D4A5C" — so a later edit doesn't "correct" a deliberate derivation back to neutral.

<!-- end-preserved-source: 71-135 -->

