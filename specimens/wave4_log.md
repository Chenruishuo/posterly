# Wave 4 — 竖版三张 PowerFlow(2026-07-17)

同一篇论文(/cephfs/chenruishuo/papers/powerflow/paper/ICML 2026/),**首个竖版生产 wave**(24×36 in portrait),
3 个 Opus agent 并行、互不可见,指纹轴照 wave-3 方法**预先互斥锁死**,并避开 wave 1/2/3 全部烧毁组合
(wave2_log.md / wave3_log.md)。

本 wave 同时是**轴 1 竖版翻译表(P1–P7,2026-07-17 Codex 6 轮审毕)的首次实战**:三个槽位刻意压上
三种机制覆盖面最大的骨架 —— P1(全宽 column 角色映射)、P3(band 角色全宽舞台带)、
P5(竖轨刊头,Gate E 自动竖轨模式)。
(2026-07-17 更新:`band` 角色与 rail-aware Gate E 已落地为工具代码,原"盲区人工检查/重判协议"作废,见下方竖版新规。)

## 预锁槽位表

| # | 概念域 | 骨架(轴1) | 底色(轴2) | 色相(轴3) | display(轴4) | 密度 | 接合(轴7) | 页头/页脚(轴8) | hero 类型 | device |
|---|---|---|---|---|---|---|---|---|---|---|
| p1 | 药典剂量 apothecary dose | **P1 全宽横带堆叠** | 淡鼠尾草满铺+白卡浮色底 | dual-semantic 茜草玫瑰(浓缩/sharpen)+灰石蓝(稀释/flatten) | Marcellus(镌刻罗马体) | dense | margin-detached 侧标签耳(药签索引;兼作带堆叠导航信号) | 药房招牌色带刊头(brand band 特许复用·re-skin)/ 一行医嘱 manifesto | 剂量刻度尺横带(线性 α 刻度 0.5/1/2/4/6,两端语义色) | evidence wall 小型药检数阵 |
| p2 | 水闸 canal lock | **P3 中段舞台带** | 白底 + 深橄榄墨闸室 stage 带(split) | same-center TONAL 橄榄墨单族 | Big Shoulders(高条 display) | balanced | chevron 导流箭旗 | 居中经典行刊头(特许复用·铭牌化)/ 极简居中「水位读数」行(特许复用) | 闸室剖面中带(自绘 SVG:上游→闸门 α→下游两流态+实测数嵌入) | numbered reading path(闸序 ①②③) |
| p3 | 词典词条 lexicon entry | **P5 标题脊柱** | 暖灰亚麻纸 | ACCENT-ONLY 朱砂 + 炭墨(词典红) | Literata(书籍衬线) | sparse | 发丝下划线族(特许复用·词典化:悬挂词头+音标眉线 two-tier,无 chip 无问句) | 标题列刊头 = 旋转书脊(w2⑤ 族特许复用·竖版重制)/ colophon 版权页行(contact 族 re-skin) | 核心主张引证条(display quotation,词典引证格式) | TL;DR「速查」通栏 |

- 密度 dense / balanced / sparse 三档齐;色相角色 dual / tonal / accent-only 三型齐。
- **sanctioned fallback**(仅骨架被门禁证实不可行时,记入 DESIGN DIRECTION):p1 无(低风险);
  p2 → P2 顶部英雄带(闸室剖面上移,band 机制不变);p3 → P6 剧目单题区(词典概念保留)。
- 近邻决定在案(均与烧毁项明确拉开,agent 不得再漂移):灰石蓝 vs w2① 高饱和钢蓝(低饱和拉开);
  朱砂(亮橙红)vs w3① 牛血红(深褐红)/ w2④ 绯红;橄榄墨(黄绿)vs w2⑤ 森绿 emph;
  Big Shoulders vs w1 Archivo Narrow(均窄高但族系不同);词典 vs w2① 专著(词条结构 vs 学术专著);
  暖灰亚麻 vs w2⑤ 暖棕(明度大幅拉开);白底(p2)与 w2③ 白测绘 coverage/treatment 不同(split 闸室带)。
- 页头/页脚族 11 张后已全部烧过一轮,本 wave 三席全部按 wave3 #5 先例**特许复用 + 重制**,within-wave 三族互斥。

## 每张 prompt 附带的坑位清单(wave2/3 教训 + 竖版新规)

- 数据陷阱:TTRL 41.18(非 EMPO 40.88)/ PowerFlow 42.17 / 真实 α 集 0.5/1/2/4/6(无 0.7)/
  beats GRPO = 3 of 4 + 第 4 项 comparable / wins-all-three 限定 Qwen2.5-Math-1.5B /
  lexical-diversity 图 y 轴口径反 / **"four model families" 禁用 — 实为 4 模型,写 "(tested/instruct) models"** /
  通讯作者 = Longbo Huang ✉(对照 \icmlcorrespondingauthor)/ 论文自身两处不一致(α=2/α=6 数值与图标签
  互换 @main.tex:761;instruct α=2 @422 vs 附录 α=4 @770)— 海报采正文口径,不在海报上调和矛盾。
- 工程陷阱:数字工具类必须定义(rule 14 FAIL)/ 逐对核合成底色(Gate G)/ 禁 nbsp 胶水链(改写优先)/
  自定义骨架抄 BASE DEFENSES 并扩展选择器 / 空带用整角色字号杠杆 / 字体 fontsource 本地 vendor 禁 CDN /
  python 用 /root/miniconda3/envs/posterly/bin/python / **不要调用注册的 /posterly skill 入口,
  一切读写与门禁都用 worktree 绝对路径**(wave3 有 2/5 agent 被带偏)。
- 竖版新规(本 wave 首验):外层 body 行轨一律 minmax(0,·);`column` 只给底边同线的贯底卡栈;
  全宽 hero/舞台带标 **band**(直挂 poster 下,不要标 hero,也不要标 banner;内部构件不带角色);
  中段带上方支撑区整块包 band;band 内容已被裁剪/坏图/letterbox 门禁覆盖(门禁只扫 band 容器本身,
  作者自建内层裁剪盒不在内 — 带内视觉仍建议以 render_preview 的 print 仿真 PDF/PNG 过目);
  竖版页头窄(logo-stack 落 QR 上方)、页脚每块一行;p3 竖轨刊头由 Gate E 自动识别(header 高 > 1.5× 宽,
  polish 摘要须出现 `vertical rail` 行;LOGO/BROKEN、四边溢出照常检查,无需人工重判)。

## 完成记录

(待各 agent 交付后由主 agent 复跑加固版门禁确认后填写)
