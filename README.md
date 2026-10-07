# K12 中文古诗文 · k12-chinese-poetry

> 小学到高中必背古诗文，以**应试**为核心。
> 诗文原文为**公有领域**；注释、译文、赏析与选篇编排 © 丢词大作战，采用 **CC BY 4.0**。

**English**: Chinese K-12 classical poetry and Classical Chinese prose, curated from
the National Curriculum Standards (Ministry of Education). Original texts are
**public domain**; our annotations, translations and commentary are **CC BY 4.0**.

[![课标篇目](https://img.shields.io/badge/课标-207%20篇-0f766e)](docs/syllabus-2022.md)
[![法律风险](https://img.shields.io/badge/版权风险-0%20风险-2ea44f)](pending/INDEX.md)
[![许可](https://img.shields.io/badge/许可-CC%20BY%204.0-blue)](LICENSE)

---

## 这是什么

一个**纯 Markdown** 的中国K12 古诗文内容库，是学习站点与游戏的**单一事实源**：

| 消费者 | 说明 |
|---|---|
| **学习站点** | [k12.diuci.com](https://k12.diuci.com)（[diuci/k12-site](https://github.com/diuci/k12-site)）——原文、注释、译文、赏析，可阅读、打印、搜索 |
| **游戏内容** | 《丢词大作战》（[diuci.com](https://diuci.com)）的诗词玩法数据，经 `tools/build.py` 编译为 `data/poems.json` |

本仓只存放内容与内容工具；站点代码、游戏代码各自独立成仓。

## 收录范围（K12 应试核心）

| 学段 | 篇数 | 依据 |
|---|---|---|
| 小学 1–6 年级 | 75 | 义务教育课标 2022 附录 1（均为诗歌） |
| 初中 7–9 年级 | 60 | 同上（含短篇散文） |
| 高中 | 72 | 高中课标 2017（文言文 32 + 诗词曲 40） |
| **合计** | **207** | 其中**文言文 52 篇** |

另收**教材拓展**篇目（统编教材里有、但课标未列的，如《梅花》《画》），单独标注。

清单见 **[docs/syllabus-2022.md](docs/syllabus-2022.md)**（义务教育）与
**[docs/syllabus-2017.md](docs/syllabus-2017.md)**（高中）——
它们是本仓的**契约文件**，`validate.py` 会逐条比对，漏收或多收即校验失败。

> **注意命名**：`k12-chinese-poetry` 里的 `poetry` 只统称「诗文」。
> 本仓**也收录文言文**（52 篇），但英文 `poetry` 与 `prose` 分属两个文学体裁，
> 文言文两边都不属于——故不写 `prose`，以免被误读为「诗词+散文」。

## 文言文怎么融入游戏

段落动辄数百字，无法贴到地面、也无法判定联句。所以每篇文言文**抽出课标实际
要求背诵的名句**作为游戏单元：

| 出处 | 名句（多为对举） |
|---|---|
| 岳阳楼记 | 先天下之忧而忧，后天下之乐而乐 |
| 滕王阁序 | 落霞与孤鹜齐飞，秋水共长天一色 |
| 陋室铭 | 斯是陋室，惟吾德馨 |
| 醉翁亭记 | 醉翁之意不在酒，在乎山水之间也 |

名句多为**对举**，天然适配联句机制；且本来就是考点。`lines` 存名句、
`pairs` 存配对，与诗词**完全同构**——游戏代码无需为古文写任何特殊分支。
全文另存于正文，供学习使用。

每篇另有 `recite` 字段标注背诵要求（`full` 全文 / `section` 段落 /
`line` 名句 / `none` 只理解），直接对应中考「名句默写」与高考「语境默写」。

## 数据来源与版权

七类来源交叉校验，每篇篇目都在 frontmatter 里记录来源代号。
完整说明见 **[docs/sources.md](docs/sources.md)**，汇总台账见 **[PROVENANCE.md](PROVENANCE.md)**，冻结快照见 **[docs/freeze.md](docs/freeze.md)**，冻结后的变更流程见 **[docs/change-process.md](docs/change-process.md)**，版本差异（异文）怎么处理与考证规则见 **[docs/variants.md](docs/variants.md)**。

> **公有领域逐篇核验**：判定只有一条——作者卒年 ≤ 当前年 − 50（《著作权法》
> 自然人作品保护期）。每篇 frontmatter 记 `authorDied`，佚名类记年代上限
> `authorEraEnd`，作者总表见 `data/authors.json`。`tools/validate.py` 第 8 项
> 逐篇核验，不满足即构建失败。仍在保护期内的作品**不收录原文**，
> 仅在 [pending/](pending/INDEX.md) 登记。我们不做「绝对安全」这类担保——
> 能做的是把每一篇的依据摆出来，让任何人可以复核。

## 目录结构

```
poems/小学/一年级上册/春晓.md# 按学段/册次组织的篇目（唯一事实源）
├── data/poems.json                # 构建产物（勿手改）
├── data/checksums.json            # 内容哈希，游戏端校验用
├── docs/
│   ├── syllabus-2022.md           # ★ 课标 135 篇契约（校验基准）
│   ├── sources.md                 # 数据来源与许可
│   ├── freeze.md                  # 内容冻结快照（content-v1 的账目与指纹）
│   ├── change-process.md          # 冻结之后改内容的流程
│   ├── variants.md                # 异文考证：版本差异怎么处理、要写下什么
│   ├── index.md                   # 总览与学习路径
│   ├── guide-for-parents.md       # 家长指南
│   └── contributing.md            # 贡献规范
├── tools/
│   ├── build.py                   # Markdown → poems.json
│   ├── validate.py                # 七项校验
│   ├── gen-pinyin.py              # 生成 data/pinyin.txt
│   └── migrate.py                 # 从游戏内 poems.js 迁移用（一次性）
└── pending/                       # ⏸️ 保护期内作品，暂不收录
```

> **本仓只管内容。** 站点代码在 [diuci/k12-site](https://github.com/diuci/k12-site)，
> 由它在 CI 中检出本仓并生成页面。

## 工具

内容工具零依赖，纯 Python 3 标准库（无需 pip install）。

```bash
python tools/build.py             # 生成 data/poems.json + checksums.json
python tools/validate.py          # 七项校验，须全绿
python tools/validate.py --partial# 增量期校验，跳过"课标完整性"
python tools/gen-index.py         # 生成 poems/索引.md
python tools/gen-pinyin.py        # 生成拼音表（需先 --fetch 下载 Unihan）
```

### `validate.py` 的七项校验

| # | 检查 | 失败示例 |
|---|------|---------|
| 1 | 课标完整性 | 课标要求收录但缺失 / 多收框架外作品 |
| 2 | id 唯一性 | 两篇共用一个 id |
| 3 | pairs 索引 | `pairs` 下标越界 |
| 4 | 每联字数 | 标五言却不是 10 字/联（已知不规则可加 `irregular` 说明） |
| 5 | 台账完整 | 缺 `source` / `license` |
| 6 | **版权核验** | `license != public-domain` 却出现在 `poems/` |
| 7 | frontmatter | 必填字段缺失 |
| 8 | **公有领域证据** | 作者卒年晚于「当前年 − 50」，或缺 `authorDied` |

## 篇目格式

每篇就是一个 Markdown 文件，**人读与机读同一份**，不需要维护两份数据：

```markdown
---
id: chunxiao
title: 春晓
author: 孟浩然
dynasty: 唐
form: 五言
stage: 小学
grade: 1
volume: 一年级下册
theme: [春天, 惜春]
emotion: 春日清晨的喜悦与怜惜
technique: [拟人]
difficulty: 1
exam_freq: 0.95
pairs: [0-1]                      # 联句配对（整句为单位）
render_split: [2, 2]              # 地面渲染时按逗号拆行
source: S3+S1+S2                  # 来源台账
license: public-domain
copyright: { text: public-domain, annotations: cc-by-4.0 }
---

# 春晓

> 孟浩然 · 唐 · 五言 · 小学一年级 · 一年级下册

春眠不觉晓，处处闻啼鸟。

夜来风雨声，花落知多少。
```

### 字段说明

| 字段 | 用途 |
|------|------|
| `id` | 稳定标识，联机同步与游戏内引用都用它|
| `lines` | **整句**（剥离标点），联句与涂地的单位 |
| `pairs` | 联句配对，`0-1` 表示第 1、2 句构成一联 |
| `render_split` | 每整句在游戏地面按逗号拆成几行（渲染层用） |
| `theme` / `emotion` | 主题与情感，玩法分类与着色 |
| `difficulty` | 1–5 难度，用于匹配玩家水平 |
| `exam_freq` | 中考出现频率估值，用于排序 |
| `irregular` | 已知的不规则之处（如《咏鹅》首句三字重叠），声明后不算错误 |

> **关于 `pairs` 与 `render_split`**：数据层以**整句**为单位（一句五言 =
> 「两句五字」共 10 字），游戏地面为了排版好看会按逗号拆开。
> `render_split` 就是这两层之间的桥。

## 参与共建

发现错字、想补注释译文、或想加篇目，都欢迎提 PR。
请先读 **[docs/contributing.md](docs/contributing.md)**。

⚠️ 数据来源与版权有严格要求，请勿直接粘贴商业站点的译文与赏析。

## 网站

学习站点：**<https://k12.diuci.com>**

站点代码在独立仓库 **[diuci/k12-site](https://github.com/diuci/k12-site)**，
用 [VitePress](https://vitepress.dev/) 构建，部署到 GitHub Pages。
它在 CI 中检出本仓的 `poems/` 与 `data/`，再生成站点页面——内容与呈现彻底分离，
因此站点侧可以自由加入样式、广告与埋点，而不会影响内容仓的授权边界。

| 页面 | 内容 |
|---|---|
| `/` | 253 篇总览，按**学段 / 主题 / 体裁**三轴筛选 |
| `/poems/…` | 单篇页：原文（**带拼音**）+ 注释 + 译文 + 赏析 + 玩法数据 |
| `/print` | A4 打印版，可装订成册 |
| `/guide` | 家长指南 |
| `/sources` | 数据来源与版权说明 |

- **拼音**取自 Unicode Unihan 的 `kMandarin`（《通用规范汉字字典》读音），
  1862 个用字 100% 覆盖
- **打印样式**已适配：隐藏导航、保留拼音与注释译文
- 站点侧的 `tools/build-site.py` 从本仓 `poems/` 生成站点副本，**不改动源文件**；
  通过环境变量 `CONTENT_ROOT` 指定内容仓位置

## 关联项目

| 项目 | 说明 |
|------|------|
| [k12.diuci.com](https://k12.diuci.com) | 学习站点（[diuci/k12-site](https://github.com/diuci/k12-site)） |
| [diuci.com](https://diuci.com) | 《丢词大作战》——用涂地射击玩诗词的 4v4 游戏 |
| `inkwave-main` | 游戏主仓库，消费本仓 `data/poems.json` |

## 许可

- **诗文原文**：公有领域（作者卒年 ≤ 当前年 − 50，逐篇可核验）
- **注释 / 译文 / 赏析 / 选篇编排**：[CC BY 4.0](LICENSE)
- **本仓脚本**：MIT，见 [LICENSE](LICENSE) 与 [tools/](tools/)

使用时请署名"来源：k12-chinese-poetry / 丢词大作战"。