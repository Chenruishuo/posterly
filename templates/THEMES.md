# Theme reference — accent bundles & re-theming mechanisms

*(added 2026-07-15; conclusions ported from ResearchStudio paper2poster's
`apply_theme.py` after its live poster wave — mechanisms re-stated for
posterly's token system, palette values carried over as a starting pool.)*

posterly templates already centralize every chrome color in the `:root`
token block, so a re-theme is mostly a **token swap**: rewrite
`--accent` / `--accent-deep` / `--accent-light` / `--accent-soft` — plus,
*when the clash rule fires* (warm accent), the `--gold`/`--gold-soft`
register pair, which today needs one CSS check beyond the token block (see
the caveat in Mechanism 1). This file records the three mechanisms worth
keeping when the theme-pack work lands, plus a field-tested accent pool.

## Mechanism 1 — the result register stays FIXED across themes

Their `--callout` (a crimson "this is the number" cue) is deliberately **not**
swapped by any theme; posterly's analog is **`--gold` / `--gold-soft`** (the
`.ours` row, `★` callouts, `.keyword-gold`). Keep it constant when re-theming:
the reader's "result highlight" association survives across a wave of posters
(the *hue-distinction* side of that promise is what the clash resolution below
exists to protect — see the mixed-wave trade-off). **SKILL.md's clash rule
still wins** (§Palette derivation: a *warm* accent — red/orange/yellow, so the
burgundy/rust/plum rows below — requires swapping the secondary to a deep cool
neutral, e.g. `#3D4A5C`, with `--gold-soft` re-derived as its ~90% white
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

**Caveat — swapping the register is NOT yet a pure token swap.** Today's
templates pair the two families directly, in BOTH directions:
`.callout.gold { background: var(--gold); color: var(--accent-deep) }`
(register as ground, accent as ink) and
`.callout strong { color: var(--gold) }` on an accent-colored band
(register as ink on accent ground). Move `--gold` to a deep cool neutral
and either direction becomes dark-on-dark (~1.0–1.6:1 against every accent
in the pool). Until the theme-pack Phase 1 decoupling adds a register-ink
token, a register swap requires **auditing every `var(--gold)` /
`var(--gold-soft)` use in the template CSS** and re-deriving each pairing's
ink at 4.5:1 — a handful of deliberate CSS touches, not a redesign.

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
`h2`/border color on white cards. **Not yet wired**: today's templates
hard-code white on the accent in a few chrome spots and define no
`--accent-ink` — replacing those literals with `var(--accent-ink)` belongs to
the theme-pack Phase 1 token decoupling; until then a *custom* pale accent
needs a manual contrast check.

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
