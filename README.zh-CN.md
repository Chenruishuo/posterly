<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/posterly-logo-dark.png">
    <img src="docs/posterly-logo-light.png" alt="posterly" width="460">
  </picture>
</h1>

<p align="center"><b>用单个 HTML/CSS 文件制作学术会议海报，<br>再通过无头 Chromium 渲染为可直接印刷的 PDF。</b></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL_v3-blue.svg" alt="许可证：AGPL v3"></a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python：3.10+">
  <img src="https://img.shields.io/badge/coding_agent-skill-7B2CBF.svg" alt="编程智能体 skill">
</p>

<p align="center">
  <a href="https://tryposterly.com"><img src="https://img.shields.io/badge/Try_it-tryposterly.com-0e7490?style=for-the-badge&logo=googlechrome&logoColor=white" alt="在 tryposterly.com 体验 posterly"></a>
  &nbsp;
  <a href="https://tryposterly.com/blog"><img src="https://img.shields.io/badge/Read_the_blog-how_posterly_works-b45309?style=for-the-badge&logo=readthedocs&logoColor=white" alt="阅读 posterly 博客"></a>
</p>

<p align="center"><a href="README.md">English</a> · 简体中文</p>

p⊕sterly 能把论文制作成可直接印刷的会议海报，尺寸与你设置的画布完全一致——无论是 ICML、NeurIPS、ICLR、CVPR，还是自定义规格。打印前，命令行检查会找出内容溢出、元素错位和未使用指定配色等问题。

**有两种使用方式：**

- **开源 skill（本仓库）。** 克隆仓库后，通过编程智能体使用——Claude Code、Codex 或任何支持 skill 的智能体均可。它在本机运行，不需要 posterly 账户。
- **托管应用。** [**tryposterly.com**](https://tryposterly.com) 可以替你运行 posterly——目前处于**内测**阶段，支付功能尚未启用。

[博客](https://tryposterly.com/blog)中的介绍文章说明了 posterly 如何把论文变成经过检查、可直接印刷的海报。

---

## 最新动态

- 🚀 **[tryposterly.com](https://tryposterly.com) 已上线** —— 网站、[博客](https://tryposterly.com/blog)和托管云应用均已上线，其中云应用处于内测阶段（支付功能尚未启用）。
- 🎨 **设计多样性<em>极大地</em>提升** —— posterly 现在能针对同一篇论文组合出更多彼此明显不同的设计方向。详见[博客](https://tryposterly.com/blog)和 [`templates/DESIGN-AXES.md`](templates/DESIGN-AXES.md)。
- ⭐ **ICML 2026 约 50 张海报** —— 现场展示的海报中约有 50 张使用 posterly 制作。

---

## 示例

**九个示例，不是九套模板。** posterly 会从版式、字体排印、配色、视觉框架、信息密度和标题区等维度做出选择并组合成不同方向；下面九张展示了其中一部分组合。同一篇论文（[*PowerFlow*](https://arxiv.org/abs/2603.18363)，ICML 2026）被用于生成九张海报：论文和内容相同，只有设计不同。每张都通过了 posterly 的硬性检查。

<p align="center">
  <img src="docs/showcase/powerflow_directions.jpg" alt="同一篇论文的九张海报，每张采用不同设计" width="100%">
</p>

以下均可打开为可直接印刷的 PDF，顺序为从左到右、从上到下：

<p align="center">
  <b>横版 · 60×36</b> —
  <a href="docs/showcase/directions/evidence-board.pdf">Evidence board</a> ·
  <a href="docs/showcase/directions/musical-score.pdf">Musical score</a> ·
  <a href="docs/showcase/directions/theatre.pdf">Theatre</a> ·
  <a href="docs/showcase/directions/orrery.pdf">Orrery</a> ·
  <a href="docs/showcase/directions/certificate.pdf">Certificate</a> ·
  <a href="docs/showcase/directions/escort-broadside.pdf">Escort broadside</a><br>
  <b>竖版 · 24×36</b> —
  <a href="docs/showcase/directions/control-panel.pdf">Control panel</a> ·
  <a href="docs/showcase/directions/cartographic.pdf">Cartographic survey</a> ·
  <a href="docs/showcase/directions/heat-treatment.pdf">Heat treatment</a>
</p>

---

## 为什么使用 HTML + CSS，而不是 LaTeX？

- **预览快。** 修改 CSS 后刷新即可，不需要重新编译。
- **现代排版能力。** 可以直接使用 Flexbox、Grid、渐变、`text-wrap: balance` 和 Web 字体，不必叠加多个 LaTeX 海报宏包。
- **可用代码检查。** “这一栏是否溢出？”可以直接用 Playwright 查询几何信息，不必靠肉眼猜测。
- **精确的印刷尺寸。** 使用 `@page { size: 60in 36in }` 和 Chromium 的 `page.pdf()`，生成的 PDF 尺寸会与画布一致。

公式由 MathJax 排版，而不是交给浏览器原生处理：直接打开模板时使用 CDN，检查和预览渲染时则使用项目内置的副本，因此离线时也能完成测量。具体说明见 [`SKILL.md`](SKILL.md)。

---

## 安装

**让智能体安装。** 将下面这句话粘贴给你的编程智能体：

> 请帮我安装这个 skill：https://github.com/Chenruishuo/posterly

智能体会克隆仓库、安装 Python 依赖并运行冒烟测试。手动安装步骤如下：

```bash
# 1. Clone where your agent discovers skills — e.g. ~/.claude/skills/ for Claude Code
#    (other agents: use their skills directory)
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

每条 `poster_check.py` 命令都应输出 `PASS`，`render_preview.py` 应生成 `poster_preview.pdf` 和 `poster_preview.png`。posterly 只能通过克隆仓库安装，不提供 PyPI 包；依赖项和 pytest 配置记录在 `pyproject.toml` 中。

---

## 使用 skill

把论文的源文件目录交给智能体：

> 使用 posterly skill，根据位于 ~/papers/mypaper/ 的 LaTeX 项目制作我的 ICML 2026 海报。Logo 位于 ~/papers/mypaper/logos/，二维码应链接到 https://github.com/you/yourcode

在 Claude Code 中，可以用 `/posterly` 作为快捷命令。

LaTeX 源文件是唯一必需的输入。智能体会直接读取源码；海报中的每个数字和论断都必须能在论文中找到依据。会议名称、Logo、二维码目标地址、品牌配色、风格偏好和文字密度均为可选信息；起草前，智能体会询问其中必要的信息。

你不需要从列表中挑选风格。posterly 会先把两到三个不同的设计方向渲染成缩略图，你看过后选定一个方向，它再完成内容填充、检查和导出。工作流程概览见[博客](https://tryposterly.com/blog)，完整设计参考见 [`templates/DESIGN-AXES.md`](templates/DESIGN-AXES.md)。

目前尚未测试直接输入 PDF 代替 LaTeX 的方式。

---

## 仓库内容

```
posterly/
├── SKILL.md              ← 智能体执行 /posterly 时遵循的工作流程
├── tools/
│   ├── run_gates.py      ← 将各项检查汇总到一份报告中
│   ├── poster_check.py   ← 各项检查：preflight / measure / pack / fit-logos / polish / verify-final
│   ├── render_preview.py ← 模拟印刷效果的 PDF + 缩略图 PNG
│   ├── style_check.py    ← 设计 token 检查
│   ├── asset_check.py    ← 真实图表来源检查（可选）
│   ├── extract_pdf_figures.py, preprocess_figures.py
│   └── _posterly/        ← 内部模块
├── templates/            ← landscape_4col、landscape_hero、portrait_2col 模板
├── specimens/axes/       ← 设计选项的渲染图册
├── examples/hello_world/ ← 安装冒烟测试和测试套件所用的最小海报
├── docs/showcase/        ← 示例拼图及各设计方向的 PDF
└── tests/                ← pytest 测试套件
```

各项检查的简要说明：

- **`run_gates.py`** 将 `preflight → style → asset → measure → polish` 汇总到一份报告中（没有提供 `--manifest` 时，`asset` 会报告为 `NOT_RUN`）。起草时默认反复运行这组检查。
- **`poster_check.py`** 可以单独运行各项检查：`preflight`（静态检查）、`measure`（模拟印刷环境的几何检查）、`pack` 和 `fit-logos`（建议性预检查）、`polish`（软性视觉检查），以及 `verify-final`（渲染后的 PDF 基本检查，需要对导出的 PDF 单独运行）。

每条命令都支持 `--help`；各项阈值和调节参数见 [`SKILL.md`](SKILL.md)，模板约定见 [`templates/README.md`](templates/README.md)。

---

## 手动编辑

如需手动编辑，请从 [`templates/`](templates/) 中复制最接近需求的骨架模板，再修改其 `:root` token 块中的共享值。样式检查要求颜色和尺寸都通过这些共享值定义，而不是分别写在各个元素上。采用 token 的海报会将检查元数据保存在 `design_tokens.json` 中。

- 模板约定——[`templates/README.md`](templates/README.md)
- 设计选项——[`templates/DESIGN-AXES.md`](templates/DESIGN-AXES.md)
- 配色与 token 参考——[`templates/THEMES.md`](templates/THEMES.md)
- 完整智能体工作流程——[`SKILL.md`](SKILL.md)

（`examples/hello_world` 是用于安装和测试的最小样例，不适合作为通用起点。）

---

## 许可证

posterly 整体采用 **GNU Affero General Public License v3.0**（AGPL-3.0），© 2026 Ruishuo Chen，详见 [LICENSE](LICENSE)。你可以使用、修改和商业化它，**但任何经过分发或通过网络部署（SaaS）的衍生作品，都必须以相同许可证发布完整的对应源代码**。这样做是为了让 posterly 保持开放，并防止闭源商业利用。

本仓库还收录了少量来自 [ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep)、采用 **MIT 许可证**的检查工具；这些特定文件仍可按原 MIT 许可证使用。MIT 与 GPL/AGPL 兼容，因此项目整体采用 AGPL-3.0，而这些文件各自仍采用 MIT 许可证。详情见 [NOTICE.md](NOTICE.md) 和 [LICENSES/](LICENSES/)。

---

## Star 历史

<div align="center">

<!-- star-history:start -->
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/star-history/star-history-dark.svg">
  <img alt="Star history" src="docs/star-history/star-history-light.svg">
</picture>
<!-- star-history:end -->

</div>
