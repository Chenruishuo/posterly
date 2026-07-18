<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/posterly-logo-dark.png">
    <img src="docs/posterly-logo-light.png" alt="posterly" width="460">
  </picture>
</h1>

<p align="center"><b>Build academic conference posters as a single HTML/CSS file,<br>rendered to print-ready PDF via headless Chromium.</b></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL_v3-blue.svg" alt="License: AGPL v3"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python: 3.10+">
  <img src="https://img.shields.io/badge/coding_agent-skill-7B2CBF.svg" alt="Agent skill">
</p>

**This is a coding-agent skill, not a hosted service.** Clone, install, and either invoke `/posterly` from your agent or call the CLIs directly. There is no cloud, no signup, no telemetry.

> [!NOTE]
> **Built with Claude, works with Codex too.** posterly is developed primarily with Claude (Opus 4.7 / 4.8), but in testing Codex (GPT-5.5) drives it just as well — and any coding agent with skill support should be fine. Hit a snag? A ⭐ and an issue are always welcome!

A poster in `posterly` is **one HTML file** styled for an exact print canvas. The skill ships three neutral templates, four sanity-check CLIs, and a render pipeline that produces a PDF at exact ICML / NeurIPS / ICLR / CVPR dimensions. Inside your agent, `/posterly` walks you through venue lookup → design direction (picked by eye from rendered thumbnails) → content fill → gated render loop — see `SKILL.md` for the full workflow it follows.

---

## Showcase

**One paper, nine directions.** [*PowerFlow*](https://arxiv.org/abs/2603.18363) (ICML 2026), built from its public LaTeX source and run through `posterly` nine times. Content is held fixed — only the design changes, so the spread is pure visual identity. Every one clears every hard gate.

<p align="center">
  <img src="docs/showcase/powerflow_directions.jpg" alt="Nine PowerFlow posters — one per design direction" width="100%">
</p>

Open any direction as a print-ready PDF — in reading order, left to right and top to bottom:

<p align="center">
  <b>Landscape · 60×36</b> —
  <a href="docs/showcase/directions/evidence-board.pdf">Evidence board</a> ·
  <a href="docs/showcase/directions/musical-score.pdf">Musical score</a> ·
  <a href="docs/showcase/directions/theatre.pdf">Theatre</a> ·
  <a href="docs/showcase/directions/orrery.pdf">Orrery</a> ·
  <a href="docs/showcase/directions/certificate.pdf">Certificate</a> ·
  <a href="docs/showcase/directions/escort-broadside.pdf">Escort broadside</a><br>
  <b>Portrait · 24×36</b> —
  <a href="docs/showcase/directions/control-panel.pdf">Control panel</a> ·
  <a href="docs/showcase/directions/cartographic.pdf">Cartographic survey</a> ·
  <a href="docs/showcase/directions/heat-treatment.pdf">Heat treatment</a>
</p>

How one paper becomes nine designs — the axis menu, the anti-convergence rules — is under [**Make your poster**](#make-your-poster).

Want an editable starting point instead? `examples/` ships worked posters (an ICML landscape, a math-heavy NeurIPS) that clear every gate — copy one, swap in your content, re-render with `tools/render_preview.py examples/<name>/poster.html`.

---

## Why HTML + CSS, not LaTeX?

- **Tweak loop in seconds, not minutes.** Edit CSS, refresh — vs. LaTeX `recompile + scan log + re-open PDF`.
- **Modern layout primitives.** Flexbox, grid, gradients, `text-wrap: balance`, web-fonts — all things LaTeX poster classes (`tcbposter`, `tikzposter`, `beamerposter`) either don't have or need package-on-package for.
- **Programmatically lintable.** Every "is this column overflowing?" check that you'd do by squinting at a PDF is a Playwright geometry query here.
- **Exact print output.** `@page { size: 60in 36in }` + Chromium's `page.pdf()` produces a PDF whose dimensions are exactly the canvas — not "approximately A0 after scaling".

Trade-off: no native math typesetting; templates load MathJax 3 from a CDN by default. The check tools don't depend on that CDN: every gate render intercepts the request and serves the skill's **bundled** MathJax (`assets/mathjax/tex-svg.js`, 3.2.2), so measurement typesets math deterministically even offline. Only a *hand-opened* poster.html needs the network — to make that offline too, copy the bundle next to the poster and change the template's `<script src=…>` to `mathjax/tex-svg.js` (there's an inline comment next to the CDN link in each template showing exactly which line to edit).

---

## Install

**The lazy way — hand it to your agent.** Paste this to your coding agent (Claude, Codex, …):

> Install this skill for me: https://github.com/Chenruishuo/posterly

It will clone the repo into `~/.claude/skills/`, install the Python deps, and run the smoke test. The manual steps below are the fallback (or for a non-agent setup).

```bash
# 1. Clone into ~/.claude/skills/ for Claude Code auto-discovery
#    (other agents: point them at this dir however they load skills)
git clone https://github.com/Chenruishuo/posterly ~/.claude/skills/posterly
cd ~/.claude/skills/posterly

# 2. Python deps
python -m pip install "playwright>=1.40"
python -m playwright install chromium
# On a fresh Linux box you may also need the system libs Chromium links against:
#   python -m playwright install --with-deps chromium
#   # or sudo apt install libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
#   #                     libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
#   #                     libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2

# 3. System dep for verify-final's pdfinfo
#    Linux:   apt install poppler-utils
#    macOS:   brew install poppler
#    Windows: choco install poppler

# 4. Smoke test
cd examples/hello_world
python ../../tools/poster_check.py preflight  poster.html
python ../../tools/poster_check.py measure    poster.html
python ../../tools/poster_check.py polish     poster.html
python ../../tools/render_preview.py          poster.html
python ../../tools/poster_check.py verify-final poster_preview.pdf --from-html poster.html

# 5. (dev) run the test suite
python -m pip install "pytest>=7" && python -m pytest
```

All four `poster_check.py` calls should print `PASS` and `render_preview.py` should write `poster_preview.pdf` + `poster_preview.png` into the directory. If that works, install is good.

**Tests (dev):** posterly is clone-only — no PyPI; `pyproject.toml` holds the deps + pytest config. The suite covers the four gates' logic plus Poppler- and Chromium-gated end-to-end checks against `examples/hello_world` (auto-skipped when those binaries aren't present).

---

## Make your poster

Once installed, just point your agent at the paper's source directory:

> /posterly — make my ICML 2026 poster from the LaTeX project at ~/papers/mypaper/. Logos are in ~/papers/mypaper/logos/, QR should point to https://github.com/you/yourcode

The paper source is the only required input — hand over the LaTeX project directory (an easily-parsed format like Word should also do) and posterly reads the actual source, so numbers and claims come from the paper, not from memory. Everything else is optional steering; whatever you don't say up front is asked in one batch of design questions before drafting:

- **Logos & QR** — file paths and a target URL, or "none" (degrades gracefully: text venue badge, no empty boxes; the QR is generated offline, never a remote QR-service link).
- **Style leanings** — must-haves or vetoes in plain words: "keep it light", "a dark editorial look is welcome", "no mascots". You are never asked to pick a style from a text list — see below.
- **Palette** — your lab/venue colors as the seed; without them one is derived from your logo, affiliation brand, or the paper's own figures (the shipped steel-blue is a last resort, not a default).
- **Text density and block count** — two independent switches: Normal vs **Light** (fewer words, the space goes to larger paper figures) and Normal vs **Fewer** (fewer, larger cards — same content, less subdivided).

**How the look is chosen — and where you come in.** posterly composes a design rather than picking a theme, from **8 orthogonal axes** (layout, canvas, palette, type, density, card frame, heading joint, masthead) plus a device pool — `templates/DESIGN-AXES.md` is the menu with its clash rules, `specimens/axes/` the rendered catalog. Each candidate starts from a one-line *concept* and designates one *hero moment*. **This is the second point you steer** (after the upfront questions): the agent renders 2–3 genuinely different directions as thumbnails and you pick one by eye — or send them back to recompose. The look is chosen visually, never from a text list. The locked direction then rides in the poster — a `DESIGN DIRECTION` comment plus `design_tokens.json` that every gate reads — so later edits and the style gate don't "correct" it. In a batch, anti-convergence rules push consecutive posters apart.

> [!NOTE]
> Building straight from a **PDF** is untested. It may still work if your agent has a screenshot / figure-extraction tool, or if the poster doesn't need to reuse the paper's figures — if you try it, an issue with your result is welcome!

---

## What's in here

```
posterly/
├── SKILL.md             ← workflow your agent follows when you /posterly
├── tools/
│   ├── poster_check.py  ← preflight / measure / pack / polish / verify-final CLIs
│   ├── render_preview.py← print-emulated PDF + thumbnail PNG
│   └── _posterly/       ← internal modules
├── templates/           ← landscape_4col, landscape_hero, portrait_2col
├── examples/
│   ├── hello_world      ← smallest poster that clears every gate (install check)
│   ├── powerflow_icml2026 ← real ICML 2026 poster (4-col landscape)
│   ├── tdgfn_icml2026     ← real ICML 2026 poster (4-col landscape)
│   └── optail_neurips2024 ← real NeurIPS 2024 poster (3-col, math-heavy)
├── docs/showcase/       ← the showcase montage + a print-ready PDF per direction
└── tests/               ← pytest suite (canvas / preflight / polish / verify-final)
```

The six sanity-check CLIs at a glance:

- `preflight`     — static lint: LaTeX residue, raw `<` inside math, missing local images, remote-image warnings (a print poster should be self-contained), missing `data-measure-role` markup.
- `measure`       — print-emulated geometry: column-bottom spread, gap to footer, poster bbox aligned to the page. On failure it prints the shared passing band + per-column safe deltas and an edit-targets block (source line + anchor per card); a persistent circuit breaker stops a non-converging loop after 30 consecutive failures (exit 3).
- `pack`          — advisory feasibility pre-check (run once before the measure loop): probes each card figure at its Gate A width-band endpoints in the browser and names columns that figure sizing alone can't bring into band.
- `fit-logos`     — advisory, read-only logo packer: proposes the max-uniform-height row arrangement for the header logos as a class+CSS snippet; the agent judges optical weight and applies it by hand — or not at all.
- `polish`        — soft visual checks: figure-AR sizing, broken/zero-size images (FIG/BROKEN), typography orphans, space-between fill, card whitespace (CARD/TRAILING — blank below a stretched card's content; CARD/INNER-VOID — a void in the middle of a stretched equal-height card whose tail is bottom-pinned).
- `verify-final`  — `pdfinfo`-based PDF sanity: page count, dimensions, file size.

Three further gates layer on top, documented in `SKILL.md`: `run_gates.py` (the default Step-4 loop driver — runs every gate into one report), `style_check.py` (a hard design-token gate, on by default), and `asset_check.py` (real-figure provenance, opt-in via `--manifest`). The `poster_check.py` CLIs above are the minimal fallback for a non-tokenized / imported template.

Detailed thresholds and tuning flags are in `SKILL.md`. See `templates/README.md` for the template gallery and the conventions a new template must follow.

---

## Customizing your poster

Every visual decision routes through the `:root` token block — restyle there, not on individual elements (the style gate enforces this). The knobs:

- **Palette**: the rebrand surface is eight tokens — `--accent` / `--accent-deep` / `--accent-light` / `--accent-soft` / `--accent-ink` plus the emphasis register `--emph` / `--emph-soft` / `--emph-ink`. `templates/THEMES.md` holds a calibrated pool of register choices.
- **Fonts**: the `--font-serif` / `--font-sans` stacks. A face outside the built-in whitelist is fine — vendor the files locally (never a CDN) and declare the family under `"fonts"` in `design_tokens.json` so the style gate accepts it.
- **Shape & figure mounts**: `--rs` scales every corner radius (1 = shipped soft look, 0 = square); `--fig-bg` / `--fig-frame` restyle how paper figures are mounted on cards (`--fig-frame: transparent` = frameless); `--u` is the global size unit.
- **`design_tokens.json`**: lives next to `poster.html` and is passed to every gate run (`run_gates.py … --tokens design_tokens.json`). It declares the poster's two hue centers, vendored fonts, and `"dark_ground": true` for a deliberate dark canvas.
- **Logos**: drop into the same directory as `poster.html`, reference as `images/your_logo.png`; the advisory `fit-logos` CLI proposes a header arrangement you can take or leave.
- **QR code**: give `/posterly` your paper/code URL and the agent generates the QR offline — the showcase posters' codes were made this way. By hand: `qrencode -o qr.png -s 12 "<url>"` (Linux) or `python -c "import qrcode; qrcode.make('<url>').save('qr.png')"`, then point the QR `<img src=…>` at it. Templates ship an inline SVG placeholder so they render offline.

---

## License

posterly is licensed as a whole under the **GNU Affero General Public License
v3.0** (AGPL-3.0) © 2026 Ruishuo Chen — see [LICENSE](LICENSE). You may use,
modify, and commercialize it, **but any distributed or network-deployed (SaaS)
derivative must release its complete corresponding source under the same
license**. This is deliberate: it keeps posterly open and prevents closed-source
commercial exploitation.

This repository also vendors a few **MIT-licensed** gate tools from
[ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep); those
specific files remain available under their original MIT license. MIT is
GPL/AGPL-compatible, so the project as a whole is AGPL-3.0 while the vendored
files stay individually MIT. Details: [NOTICE.md](NOTICE.md) and
[LICENSES/](LICENSES/).
