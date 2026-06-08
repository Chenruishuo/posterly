# NOTICE — third-party provenance

posterly is licensed **as a whole under AGPL-3.0 © 2026 Ruishuo Chen** (see `LICENSE`). It
additionally vendors a set of poster-quality "gate" tools, three tokenized templates, and one
component catalog from **ARIS** (Auto-claude-code-research-in-sleep), whose `paper-poster-html`
skill is itself a fork of posterly. Those ARIS files are **MIT-licensed**; MIT is
GPL/AGPL-compatible, so they are lawfully combined into this AGPL project while remaining
individually available under their original MIT terms (see below). This file records the vendor
boundary so the relationship stays clean and attribution is preserved in both directions.

## Licensing of this combined work

- The project **as a whole** is **AGPL-3.0** (`LICENSE`). Any distributed or network-deployed
  (SaaS) derivative of posterly must release its complete corresponding source under AGPL-3.0.
- The **body-unmodified ARIS tools** below (`style_check.py`, `asset_check.py`,
  `extract_pdf_figures.py`, `preprocess_figures.py`) are verbatim **MIT © 2026 wanshuiyin** and
  remain **additionally available under MIT** (`LICENSES/aris-MIT.txt`) — anyone may extract just
  those files and use them under MIT. AGPL copyleft applies to posterly as a whole, not to these
  individual third-party files in isolation.
- The **adapted** files (templates, `COMPONENTS.md`, `run_gates.py`) are derivative works
  combining posterly-original material with ARIS's MIT contribution; as part of posterly they are
  distributed under AGPL-3.0, with the MIT origin attributed below.

## Vendored from ARIS (MIT)

- **Upstream**: ARIS — https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep
  (skill `paper-poster-html`).
- **License**: MIT, © 2026 wanshuiyin. Full text: `LICENSES/aris-MIT.txt`.
- **Note on lineage**: ARIS's `paper-poster-html` vendored posterly's render/measure engine
  (`_posterly/`, `poster_check.py`, `render_preview.py`) unchanged, then layered the gate
  tools below on top. We vendor those ARIS-original additions back here. posterly keeps its
  **own** (newer) `_posterly/` and `poster_check.py` — they are NOT replaced.

Vendored, **body unmodified** (a provenance header comment was prepended to each `.py`):

| Path | Origin in ARIS | Purpose |
|------|----------------|---------|
| `tools/style_check.py` | `scripts/style_check.py` | style HARD gate (12 rules: token-only colors, no inline `style=`, no gradients, font whitelist, `--fs-*` scale, data-attribute contracts) |
| `tools/asset_check.py` | `scripts/asset_check.py` | real-figure provenance gate (`data-source="paper"` + `FIGURE_MANIFEST.json` sha256 chain + rendered-area bands) |
| `tools/extract_pdf_figures.py` | `scripts/extract_pdf_figures.py` | pull real figures out of a paper PDF (contact-sheet / auto / crop) — needs PyMuPDF + Pillow |
| `tools/preprocess_figures.py` | `scripts/preprocess_figures.py` | autocrop / resolution-check extracted crops, keep `FIGURE_MANIFEST.json` honest — needs Pillow |

These vendored scripts import posterly's own `tools/_posterly/` (canvas/render/textutil),
so they run against posterly's engine, not a copy.

Vendored and **adapted**:

| Path | Origin | posterly modifications |
|------|--------|------------------------|
| `templates/COMPONENTS.md` | `templates/COMPONENTS.md` | re-pointed from the ARIS skill's design docs to posterly's `SKILL.md` + `tools/` gates; provenance note added. The component classes it catalogs are posterly's own. |
| `templates/landscape_4col_neutral.html` | `templates/landscape_4col.html` | the **tokenized** form of posterly's own neutral template — replaced the non-tokenized original in place so `style_check` passes out of the box; provenance comment prepended. Measure-role skeleton, component classes, and placeholder copy are posterly's own (verified identical). |
| `templates/landscape_hero_neutral.html` | `templates/landscape_hero.html` | same as above |
| `templates/portrait_2col_neutral.html` | `templates/portrait_2col.html` | same as above |
| `tools/run_gates.py` | `scripts/run_gates.py` | gate orchestrator → `GATE_REPORT.json`. **Modified by posterly** (fixes an upstream false-pass): the asset gate is now opt-in — without `--manifest` it is reported `NOT_RUN` and excluded from `overall`, instead of being run, crashing on its required arg (child exit 2), and silently counted as a pass; a hard gate that ends in SKIPPED from a real environment error now counts as a failure. Also forwards `--hero` to `asset_check`; the report `skill` field is `posterly`. |

## ARIS-inspired, original posterly work (not a copy)

- The **softened closed-set fix vocabulary** and the **cross-model final-review** step in
  `SKILL.md` are original posterly text, inspired by `paper-poster-html`'s DESIGN_FINAL
  (Phase 5 anti-patch-loop / Phase 6 Codex review). posterly's version is half-closed (the
  agent may *propose* a new token/variant for human review rather than being hard-blocked)
  and uses adjustable round caps, suited to a human-in-the-loop workflow.

## Not vendored

ARIS's venue color-token packs (`templates/tokens/*.json`) were intentionally **not** taken:
posterly derives its palette from poster signals (logo / figure / brand) under WCAG AA,
rather than from fixed per-venue presets.

## Upstream-sync rule

When pulling new ARIS releases of these tools, preserve the vendor boundary: re-vendor the
body-unmodified `.py` files (`style_check.py`, `asset_check.py`, `extract_pdf_figures.py`,
`preprocess_figures.py`) as drop-in replacements (re-prepend the provenance header), and
re-apply the documented `COMPONENTS.md` + template adaptations. **`run_gates.py` is not a
drop-in**: re-apply posterly's asset-opt-in / no-silent-false-pass patch on top of the new
upstream version. Do not fold posterly-specific logic into the body-unmodified files, so the
ARIS diff stays clean and re-syncable.
