# Figure, logo, and provenance work

Read [Step 2](#image-preprocessing) before processing the paper figures, QR codes, or logos used. Its optional stage title does not waive mandatory conversion, crop hygiene, matched geometry, resolution, or logo-inspection requirements inside that stage. For font preparation, the original instructions remain with the token pack in [Step 2.5 item 4](design-workflow.md#direction).

- Logo placement also requires [Gate E](visual-polish.md#gate-e); figure mounts and matched crops require [Gate A](visual-polish.md#gate-a).
- Read [real-figure provenance](#figure-provenance) when adopting that optional contract; its human checkpoints, thresholds, and manifest requirements then apply. Its optionality does not make ordinary figure fidelity or Step 2 hygiene optional.
- Delivery localization/bundling is governed by [Step 7](validation.md#final-verification), not by provenance opt-in.

[Shared reading and path rules](../SKILL.md#reading-contract-and-execution-boundaries) apply.

<a id="image-preprocessing"></a>

<!-- preserved-source: SKILL.md lines 178-213 -->
### Step 2 — Image preprocessing (optional but reduces re-renders)

For each paper figure you'll use:

1. **Vector source (EPS / PDF figure)?** Chromium `<img>` renders **neither EPS nor PDF** (converting to PDF does not help — also not embeddable), so a vector figure must be converted first. **SVG** is best — it stays crisp at poster scale. If a vector converter is already installed (`inkscape`, `pdf2svg`, `dvisvgm`), go straight to SVG. If none is installed, reuse an existing user choice/authorization for this same conversion. Only if that choice is missing or conflicting, **ask the user** (one question through an available input tool permitted for this purpose, or directly in text if none is suitable) whether to install one for a sharp vector figure, or rasterize to PNG instead — don't decide an unanswered choice silently:
   - **Willing to install → SVG** (preferred): e.g. `inkscape fig.eps --export-type=svg`, or `pdf2svg fig.pdf fig.svg`.
   - **Decline → high-res PNG**: rasterize with Ghostscript at ≥ 2× rendered px — `gs -dSAFER -dBATCH -dNOPAUSE -dEPSCrop -r600 -sDEVICE=png16m -o fig.png fig.eps` (PIL works too; it shells out to `gs`: `Image.open('fig.eps').load(scale=5)`).

   Never embed the `.eps` / `.pdf` directly — it renders blank, caught only late as `polish`'s FIG/BROKEN after a wasted render.
2. **Autocrop whitespace** with PIL.ImageChops so the figure fills its card. **Then crop hygiene, on every crop you (or anyone) cut from a PDF page or screenshot — re-open the cropped file and check all four edges** for cut-off content: a label row sliced mid-glyph, a truncated axis, a line exiting the frame. A hand-read bbox that lands a few px short cuts text in a way no resolution gate sees (a real poster shipped a qualitative panel whose dataset labels were cut in half — 7 source-px short, every gate green). And **panels that are geometric twins — matched panels off one composite figure, a same-scale comparison group — must be cut with the SAME crop box** (identical width/height and edge padding): tag them `data-crop-lock="<group-id>"` so `polish`'s `FIG/PAIR-GEOMETRY` verifies the geometry stayed consistent ([Gate A](visual-polish.md#gate-a)). Related-but-differently-composed figures are exempt — the contract is for crops that are supposed to be identical in frame, not for every pair that sits side by side.
3. **Re-export at ≥ 2× the rendered px** — the print-quality *target* (the `asset` gate's hard floor is a lower **1.5×**, so a 2× source clears it comfortably). A `200u × 120u` figure print-rendered at 96 ppi → ~756 × 454 px. Source PNGs must be ≥ 1500 × 900 to look crisp at print.
4. **QR codes**: request at ≥ 2× rendered px (e.g., 480×480 if displayed at ~240 px).
5. **Logos**: inspect each user-provided logo file before placing it, then pick a size class and chip treatment from the two tables in [**Gate E — Header logos**](visual-polish.md#gate-e). Use the same dedicated interpreter that runs the Posterly tools (replace `/absolute/path/to/dedicated-env/bin/python` with its verified absolute path); this snippet needs Pillow (`/absolute/path/to/dedicated-env/bin/python -m pip install Pillow` if missing):

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

<!-- end-preserved-source: 178-213 -->

<a id="figure-provenance"></a>

<!-- preserved-source: SKILL.md lines 714-724 -->
### Real-figure provenance gate (optional) — `asset_check.py` + figure tools

Step 1–2 sets a ≥2× resolution *target*; this gate enforces a hard **1.5× floor** (a 2× source clears it comfortably) for the workflow where you want a guarantee that every paper figure is genuinely from the paper (not AI-fabricated, not a tiny decorative thumbnail). **Needs the optional figure dependencies** declared in `pyproject.toml` under `project.optional-dependencies.figures`: `/absolute/path/to/dedicated-env/bin/python -m pip install "PyMuPDF>=1.23" "Pillow>=10"`. Install them only when this workflow needs them; Posterly itself does not need to be installed as a Python package.

1. `/absolute/path/to/dedicated-env/bin/python tools/extract_pdf_figures.py paper.pdf --out fig_work/ contact-sheet` → a labelled page grid to read crop bboxes off; then the `auto` (candidate regions) and/or `crop` subcommands at 300–450 DPI (the top-level `--out` goes **before** the subcommand). **A human confirms crop choices** (🚦).
2. `/absolute/path/to/dedicated-env/bin/python tools/preprocess_figures.py fig_work/fig.png --autocrop --manifest FIGURE_MANIFEST.json` → trims white margins, checks resolution, and (with `--manifest`) re-syncs each crop's `natural_px` / `sha256` so the manifest stays honest. Without `--manifest` it autocrops but leaves stale hashes that `asset_check` will then reject.
3. Embed as `<img data-source="paper" data-asset-id="fig1">`; record each in `FIGURE_MANIFEST.json` (page, bbox, dpi, sha256, natural_px, `from_paper: true`).
4. `/absolute/path/to/dedicated-env/bin/python tools/asset_check.py poster.html --manifest FIGURE_MANIFEST.json` → fails unless ≥2 paper figures resolve to manifest entries with matching sha256 and a rendered area **inside a band** — per-figure `≥1.5%` of the poster (floor) to `≤13%` of the body (cap), total `12–28%` of the body (warn above 24%; target ~14–22%; `--hero` raises the per-figure cap to 42% for a hero centerpiece). So a too-small figure *and* an oversized one both hard-fail — worth knowing if you enlarge figures for a Light-density poster. Theory-only papers waive the total-area rule at a human checkpoint (`--waive-total-area`), never silently.

If you don't adopt this contract, skip it — the other gates don't require `data-source` / manifest markup.

<!-- end-preserved-source: 714-724 -->

