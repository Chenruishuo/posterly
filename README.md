# posterly

> Build academic conference posters as a single HTML/CSS file, rendered to print-ready PDF via headless Chromium.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Claude Code skill](https://img.shields.io/badge/Claude_Code-skill-7B2CBF.svg)

**This is a Claude Code skill, not a hosted service.** No signup, no cloud — clone, install, invoke `/posterly` from Claude Code (or run the CLIs directly).

A poster in `posterly` is **one HTML file** styled for an exact print canvas. You iterate by **measuring**, not eyeballing — the screen preview lies; only `emulate_media("print")` at the correct viewport tells the truth. The skill ships three neutral templates, four sanity-check CLIs (`preflight` / `measure` / `polish` / `verify-final`), and a render pipeline that produces a PDF at exact ICML / NeurIPS / ICLR / CVPR / ASP-DAC dimensions.

---

## Why HTML + CSS, not LaTeX?

- **Tweak loop in seconds, not minutes.** Edit CSS, refresh — vs. LaTeX `recompile + scan log + re-open PDF`.
- **Modern layout primitives.** Flexbox, grid, gradients, `text-wrap: balance`, web-fonts — all things LaTeX poster classes (`tcbposter`, `tikzposter`, `beamerposter`) either don't have or require packages-on-top-of-packages for.
- **Programmatically lintable.** Every "is this column overflowing?" check that you'd do by squinting at a PDF is a Playwright geometry query here.
- **Exact print output.** `@page { size: 60in 36in }` + Chromium's `page.pdf()` produces a PDF whose dimensions are exactly the canvas — not "approximately A0 after scaling".

The trade-off is no native math typesetting; the templates load MathJax 3 from a CDN by default (with one-line offline swap documented inline).

---

## Quickstart

```bash
# 1. Clone or place under ~/.claude/skills/ for Claude Code auto-discovery
git clone https://github.com/<your-github>/posterly ~/.claude/skills/posterly
cd ~/.claude/skills/posterly

# 2. Install Python deps
python -m pip install "playwright>=1.40"
python -m playwright install chromium

# 3. System deps (for verify-final's pdfinfo)
#    Linux:   apt install poppler-utils
#    macOS:   brew install poppler
#    Windows: choco install poppler

# 4. Render the hello-world example
cd examples/hello_world
python ../../tools/poster_check.py preflight  poster.html
python ../../tools/poster_check.py measure    poster.html
python ../../tools/poster_check.py polish     poster.html
python ../../tools/render_preview.py          poster.html
python ../../tools/poster_check.py verify-final poster_preview.pdf --from-html poster.html
```

The four `poster_check.py` steps print `PASS`; `render_preview.py` prints the PDF and PNG paths it wrote. If you see all four `PASS` lines and a `.pdf` / `.png` pair appear in the directory, your install works.

From inside Claude Code, just type `/posterly` and the skill walks you through the workflow (venue lookup → template pick → content → renders).

---

## Tools

```
tools/
├── poster_check.py      ← CLI: measure / preflight / polish / verify-final
├── render_preview.py    ← CLI: print-emulated PDF + thumbnail PNG
└── _posterly/           ← internal modules (canvas, render, preflight, …)
```

| Subcommand | Role | Hard / soft |
|---|---|---|
| `preflight`     | LaTeX residue, math `<`, missing images, role validation | hard |
| `measure`       | Column-bottom spread + gap-to-footer + canvas-fill (≥ 95 %) | hard (spread < 5 px) |
| `polish`        | Figure-AR sizing, typography orphans, space-between fill | soft (`--strict` to fail) |
| `verify-final`  | `pdfinfo` page count / dimensions / file size | hard |
| `render_preview`| Render PDF + thumbnail PNG | n/a (warns on MathJax timeout) |

All scripts read `@page { size: W H }` from the input HTML, so the same code handles ICML 60×36 landscape, ICLR 24×36 portrait, CVPR A0, ASP-DAC 36×47 portrait, etc. — no per-venue flags. `--canvas` accepts both numeric (`60x36in`) and named sizes (`A0 portrait`, `A1 landscape`).

---

## Templates

| Template | Canvas | Layout | Use when |
|---|---|---|---|
| `landscape_4col_neutral` | 60 × 36 in landscape | 4 columns + optional banner + takeaways | The default ML conference (ICML / NeurIPS / generic). |
| `landscape_hero_neutral` | 60 × 36 in landscape | Hero (1.5 fr) + 1 supporting column | One big figure IS the visual hook. |
| `portrait_2col_neutral` | 24 × 36 in portrait | 2 columns (no banner) | ICLR / CVPR portrait spec, vertical posters. |

All templates ship neutral — no lab branding, no paper content — just `TODO` placeholders. Copy one to your working dir as `poster.html`, edit `:root` design tokens for your colors, fill the TODOs.

See `templates/README.md` for the gallery and the conventions a new template must follow (`data-measure-role` scheme, `--u` unit system, `@page` requirement).

---

## The Workflow

See `SKILL.md` for the full skill instructions Claude Code will follow. The short version:

1. **Pull the venue spec.** Canvas, font floor, anonymity rules. Wrong canvas → every alignment decision downstream is invalid.
2. **Pick a template + palette + logos + ✉ author.**
3. **Pull paper content.** Numbers, equations, figure paths from the `.tex` — never invent.
4. **Content audit (strongly recommended).** Send the draft to an external LLM reviewer (Codex MCP, GPT-5, another Claude session) for a paper-vs-poster claim → evidence check. Past sessions caught real fidelity bugs only here.
5. **Scaffold from template, fill TODOs.**
6. **Render + measure loop:** every layout change, run `measure` until `spread < 5 px`, gap-to-footer ∈ [30, 50] px, and canvas-fill ≥ 95 %.
7. **Polish:** run `polish` for soft visual checks (figure sizing, orphans, space-between).
8. **Final review:** send the rendered PDF back to the reviewer for residue + visual rhetoric.
9. **`verify-final`** the PDF, then print.

---

## Visual polish gates

`polish` surfaces three failure modes the alignment gate cannot see. See SKILL.md for the full rules; the short version:

- **Gate A — figure sizing by aspect ratio.** Wide figures (AR > 1.3) should occupy 70–100 % of card width; the gate warns below 65 %. Square (AR ≈ 1) → 55–75 %, warns below 55 %. Tall (AR < 0.8) → 45–60 % with text-right; warns above 70 % at full width.
- **Gate B — typography orphans.** Trailing `↑↓×÷±§¶†‡*°%` on stat-number elements without `white-space: nowrap` may wrap alone — jarring at 2 m.
- **Gate C — space-between fill.** A `justify-content: space-between` column whose largest inter-card gap exceeds 5 % of column height is filling whitespace because content is unbalanced. Add meaningful content, not shrink gap.

All three thresholds are CLI-tunable.

---

## Customizing

- **Colors:** edit `:root` design tokens in the template (`--accent`, `--gold`, `--bg-*`, …).
- **Fonts:** edit `--font-serif` / `--font-sans` in `:root`. Web-font links go in the template `<head>`.
- **Logos:** drop into the same directory as `poster.html`, reference as `images/your_logo.png`.
- **QR code:** templates ship with an inline SVG placeholder so they render offline. Generate a real QR with `qrencode -o qr.png -s 12 "<url>"` (Linux) or `python -c "import qrcode; qrcode.make('<url>').save('qr.png')"` and change the `src` in the QR `<img>`.
- **Math offline:** download a MathJax v3 release and replace the CDN `<script>` `src` with `mathjax/es5/tex-svg.js`.

---

## Development

posterly ships as a clone-only Claude Code skill — `pyproject.toml` carries
runtime + dev dependency declarations and pytest config, NOT package
publishing. To run the tests:

```bash
python -m pip install "playwright>=1.40" "pytest>=7"
python -m playwright install chromium
python -m pytest          # or: pytest -q
```

`tests/` covers canvas parsing (incl. named sizes + `@page` extraction), preflight math-delimiter coverage, line-number preservation, polish role-validation, and the `verify-final` input gates (`--canvas` / `--from-html` mutual exclusion, missing files). The `pdfinfo` round-trip is exercised by the `examples/hello_world` smoke test rather than a unit test.

---

## License

MIT. See [LICENSE](LICENSE).
