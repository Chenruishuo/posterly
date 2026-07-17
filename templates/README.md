# Templates gallery

Each template is a **self-contained, neutral** HTML file: no lab branding, no paper content — only TODO placeholders. Copy one to your working dir as `poster.html`, edit `:root` design tokens, swap TODOs for your content, then iterate via `tools/run_gates.py` (the default driver — runs preflight → style → measure → polish in one shot) + `tools/render_preview.py` for the PDF. (Plain `tools/poster_check.py measure` still works if you don't adopt the style/asset gates.)

Every layout-critical element carries `data-measure-role` so the measurement script can locate columns / hero / footer regions across templates.

Component contracts live in `COMPONENTS.md`; the design-axes composition menu (layout / canvas / palette / typography / density / card & frame / section-heading joint / masthead-footer, plus devices and clash rules) lives in `DESIGN-AXES.md`; re-theming mechanisms and a field-tested accent pool live in `THEMES.md` (a theme is a `:root` token swap — the result register `--emph` is chosen per poster / per wave, then held fixed within the wave; `--accent-ink` / `--emph-ink` carry the ink on those fills, and `--rs` scales every corner radius, 1 = shipped soft look, 0 = square).

## Scaffolds, not finished posters

A template is a **scaffold**: figures are commented out and copy is `TODO` stubs, so each column only fills the top of the canvas. That means:

- **`preflight` passes out of the box** — it checks structure (valid roles, no LaTeX residue, no raw `<` in math), which the scaffold already satisfies.
- **`measure` and `polish` are gates for your *finished* poster.** They check that columns bottom-align to within 5 px, that the gap to the footer sits in a tight band, and that no card is left half-empty — properties only a *filled* poster can have. An unfilled scaffold is **expected to fail them** (huge column-bottom spread, a large gap to the footer). That's not a bug in the template; it's the gate telling you the poster isn't finished yet.

So the loop is: copy → fill content + uncomment figures → run `measure`/`polish` and balance until they pass. For an all-gates-pass reference, see `examples/hello_world/` (a complete, balanced poster).

## Picking a template

| Template | Canvas | Layout | Use when |
|---|---|---|---|
| **landscape_4col_neutral** | 60 × 36 in landscape | header → optional banner → **4 columns** → optional takeaways → footer | Standard ML conference poster (ICML / NeurIPS / generic). You have ~3–5 content cards per column. Mix of figures, equations, tables. The default choice. |
| **landscape_hero_neutral** | 60 × 36 in landscape | header → **hero panel (1.5fr)** + supporting column (1fr) → optional takeaways → footer | The paper's main figure or system diagram IS the visual hook. You want one big illustration on the left and 3–4 short cards on the right. No framework banner (hero replaces it). |
| **portrait_2col_neutral** | 24 × 36 in portrait | header → **2 columns** → footer (no banner, no takeaways strip) | ICLR / CVPR portrait spec, or any venue with portrait orientation. Vertical space is precious — banner + takeaways are dropped; final card on right column acts as a takeaways callout. 2-col is the *default* portrait skeleton, not the only one: other portrait topologies (band stack, playbill, mid-stage band, …) are in `DESIGN-AXES.md` §Axis 1 · portrait translations — build those from this template's tokens and carry its BASE DEFENSES block into the custom skeleton. |

## Adding a new template

A new template **MUST**:

1. Set `@page { size: <W>in <H>in }` (or `mm`/`cm`/`pt`) inside a `<style>` block — the canvas parser fails if absent.
2. Carry `data-measure-role="poster"` on the root poster element.
3. Use these roles consistently:
   - `header` on the **whole header region** (title + authors + affiliation, plus the logo /
     venue-badge / QR blocks) — `polish`'s logo & QR gates only look *under* this role, so it
     must wrap those blocks, not just the title text
   - `banner` on a horizontal banner row (optional)
   - `body` on the body grid container
   - `column` on each vertical content column
   - `card` on each content card inside columns
   - `hero` on a hero panel (mutually-exclusive with framework banner)
   - `footer-strip` on a takeaways / highlight strip (optional)
   - `footer` on the bottom info bar (method · venue · acknowledgements · code repo · contact —
     logos and the QR live in the header, not here)
4. Use the `--u` unit system (`1.6px` screen, `1mm` print) for ALL sizing via `calc(N * var(--u))` — never bare px except for hairlines.
5. Keep all paper-specific content as `TODO` placeholders — neutral templates only.

Add a row in the table above and link it in `SKILL.md` Step 3.
