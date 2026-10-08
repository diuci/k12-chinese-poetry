# 内容变更流程（content-v1 冻结之后怎么改）

内容仓在 `content-v1` 打 tag 的那一刻起，**正文就是合同**。
这份文件规定：改一篇内容要走哪几步、谁批准、改完必须跑什么。
不是形式主义——每一条都对应一个已经发生过的真实事故。

## 0. 冻结意味着什么

| 冻结前 | 冻结后 |
|---|---|
| 发现错文，当场改 | 发现错文，走下面的流程改，并且必须发版 |
| 登记表可以写「P6 处理」 | 登记表只许写「正常」或「口径」，不许写「以后再说」 |
| 台账数字随跑随变 | 台账数字随 tag 固定，改动要重新生成并对比 |
| 站点可以直接跟 main | 站点只跟 tag，不跟 main |

冻结的是**内容**，不是仓库。代码、工具、护栏继续改。

## 1. 什么算内容变更

算：正文用字、必背名句、全文小节、注释、译文、赏析、异文、学段/册次、背诵要求、
课标契约（`docs/syllabus-2022.md`、`docs/syllabus-2017.md`）、登记表、来源强制页名。

不算：`tools/` 里的检查逻辑（除非它改变了判定口径）、README 的措辞、构建脚本的重构。

## 2. 一次内容变更必须走完的五步

### 第 1 步：先说清「为什么现在的内容是错的」

必须给出一条可核验的依据：公有领域底本的页面 URL、课标原文、教材册次。
**不接受**「我记得」「网上都这么写」「古诗文网是这么写的」（S5 只许比对，不许作为依据）。

### 第 2 步：改篇目文件，并把裁定写进篇内

改了正文用字，就要在该篇的 `## 异文` 里留下差异清单；
推翻了旧文本，就要写 `## 旧文本裁定`：旧文本原文、为什么错、依据 URL、裁定人与日期。
这一段的存在不是为了好看，是为了下一次有人把错文改回来时，能看见这里已经查过一次。

### 第 3 步：跑完整链条，一条不许跳

```
python tools/build.py
python tools/gen-index.py
python tools/validate.py
python tools/validate.py --selftest
python tools/check-duplicates.py
python tools/check-contamination.py
python tools/check-text-sources.py
python tools/build-textbook-lessons.py --report
python tools/apply-textbook-status.py --write
> **链条必须一处失败就停。** PowerShell 里一条命令失败不会拦住后面的命令，
> 最后一条的退出码会把整串盖成 0——上一轮 validate 报出「望海潮.md:106 小节名粘在行末」，
> 链条却还是绿的、还提交了。所以每一步之后都要 `if ($LASTEXITCODE -ne 0) { exit 1 }`。

python tools/build-ledger.py --selftest
python tools/build-ledger.py
python tools/build-textbook-table.py
python tools/fix-meta-lines.py --check
python tools/enrich-variants.py --selftest
python tools/check-variant-sources.py
python tools/check-variant-defaults.py
# 按需（跑一次要几百次网络请求，不进链条）：python tools/hunt-variant-sources.py
python tools/check-variant-defaults.py --selftest
python tools/verify-variant-claims.py --write --refresh
python tools/extract-fulltext-wikitext.py --selftest
python tools/verify-variant-claims.py --selftest
node tools/check-legal.mjs
```

链条里每一环都是护栏。两个容易踩的坑，都踩过：

- `check-text-sources.py --limit N` 是试跑，**不许覆盖正式表**（现在试跑写到 `data/text-sources.partial.json`）。
  以前 `--limit 3` 跑一次，正式表从 251 篇变成 3 篇，不报错，后面所有读这张表的检查安静地读到残缺数据。
- `apply-textbook-status.py` 的结论全部来自 `data/volume-findings.json`，所以必须先跑 `build-textbook-lessons.py --report` 再跑它；
  顺序反了就会拿旧结论写 frontmatter。

补全文用的 `tools/fetch-fulltext.py` 不是护栏，是取料工具：它只写候选到 `data/fulltext-candidates.json`，
候选全文进仓之前必须有人逐篇看过——它只证明「仓里的必背句在这一页里找得到」，不证明「这一页整页都是这一篇」。

`tools/enrich-variants.py` 同样是取料工具，不是护栏。它只给「来源页／维基文库」这一类异文条目补 URL，
URL 取自 `data/text-sources.json` 里这一篇**实际比对过的那一页**；引的是别的书（《白香词谱笺》《四部丛刊》…）的条目一律不补，
条目里没写「从哪个」的也不替人编一个取舍。它自带 5 个坏例子自检（该补的没补、重复补、把别的书安到维基文库头上、
没说是哪一页也补、越界改别的小节），跑 `--selftest` 拦不住就等于没有这个检查。

`tools/check-variant-sources.py` 是护栏：篇内每一条「出处：维基文库《某页》」都必须对得上——
要么这一页就是本篇正文比对过的那一页（合选页算在内），要么它在 `data/variant-sources.json` 里登记过、
且登记时写明的「这一页上确实有的那个字」今天还在页上。两条都不满足就是可疑：页名写错，或者出处是编的。
它抓到过的真错：《论语》十二章 被安上《中國文學批評史》的链接（页名撞车）、《老子》八章 引用了一个空页《老子河上公章句/道經》。

`tools/extract-fulltext-wikitext.py` 是取料工具：从 wikitext 取「本页自己认定的正文」，并把夹注异文一并收出来。
候选只写进 `data/fulltext-candidates.json`，**不写正文**；进仓前必须按句过第二来源，并且有人判断完整性。
它抓到过的真错：`{{ProperNoun|琅琊}}` 的第一个参数就是正文本体，一律丢掉不认识的模板会把专名全吞掉，
正文成了「望之蔚然而深秀者，也。」——句子还通，只有逐句核才会暴露。

`tools/verify-variant-claims.py` 是取料工具：把「别本作某」「通行本作某」这种没有出处的断言逐条回来源页核实——
找得到就补出处（页名 + 链接）；找不到就在条目里写明「仓内没核到……只作线索，不作为已考实的异文」。
它不新增任何断言。台账把「出处：仓内没核到」单列成一项，**不算带出处**：把没核实伪装成已核实，比空着更坏。

任何一条非 0 退出，这次变更就不算完成。

### 第 4 步：台账必须重新生成，并对比前后

`docs/ledger.md` 与 `data/ledger.json` 由脚本生成，**禁止手改**。
提交前把台账的「账目闭合」和「缺口统计」两段的数字贴进提交信息：
数字变了必须能解释；解释不了就是改坏了。

### 第 5 步：登记表同步

- 修好了一个登记过的缺陷 → **删掉那条登记**，否则校验器报「已知未修登记过期」；
- 新缺陷要容忍 → 必须写全 `key / title / reason / phase / added`，`phase` 只许 `正常` 或 `口径`；
- 校验器看不见的口径决定（比如某篇核不到外部底本）→ 写进篇内「收录范围」小节，不许只写在脑子里；
- 跨作者重叠 → 在 `data/overlap-verdicts.json` 里逐对裁定，没有裁定且重叠过半即失败。

## 3. 谁可以改哪一类

| 变更类型 | 允许的直接依据 | 需要额外确认 |
|---|---|---|
| 正文用字 | 公有领域底本（S9 维基文库 / S3 MIT 库） | 与统编教材用字冲突时，先记异文，再按「教材版为准」定 |
| 必背名句 | 教材要求 + 底本里确实有这句 | 名句必须能在本篇全文里逐字找到（护栏 2.7 与出处核对都会查） |
| 学段 / 册次 | 课标附录 + 教材目录 | 与课标学段不一致时，登记 `stage-cross` 口径，不许复制第二篇 |
| 背诵要求 `recite` | 教材的背诵/默写要求 | `full` 必须仓内真有全文（护栏 2.12 会查） |
| 新增篇目 | 课标附录或统编教材 | 版权核验（作者卒年 + 50 年）+ 出处核对 |
| 现当代 / 外国作品 | —— | 不收原文，只登记进 `pending/` |

## 4. 发版

```
git tag -a content-v2 -m "..."     # 内容 tag，不是代码 tag
```

tag 之后：

1. 把 `docs/ledger.md` 的「账目闭合」与「缺口统计」两段数字抄进 tag 的说明；
2. 站点侧（学古诗 / 连词成句 / 汉兜）把 `CONTENT_ROOT` 指到这个 tag 再构建；
3. 三个站点构建全绿、链接全通，才算这次内容变更真正上线。

**不许**让站点跟 `main`。main 是工作区，tag 才是发布物。

## 5. 紧急修正（发现会影响考试的内容错误）

走同样的五步，但允许先修后补文档，条件是：

- 24 小时内补齐第 2 步的「旧文本裁定」；
- 立即打一个 patch tag（`content-v1.1`），并通知站点侧重新构建；
- 在 `docs/ledger.md` 之外的地方（本文件末尾的「修正记录」）留一行记录。

### 修正记录

| 日期 | 篇目 | 错的是什么 | 怎么发现的 |
|---|---|---|---|
| 2026-10-07 | 桂枝香·金陵怀古 | 必背名句第三条是陆游《示儿》的结尾两句，注释译文赏析全建在上面 | 跨作者重叠检查点名 |
| 2026-10-07 | 谏逐客书 | 必背名句「来邳豹于吴」「贤者不译」在史记原文与同篇全文里都不存在；注释凭空编了「邳豹：春秋时吴国人」 | 出处交叉核对 0 命中 |
| 2026-10-07 | 稚子弄冰 | 「银铮」应为「银钲」（钲是乐器，铮是声音） | 出处核对核不到后逐字复核 |
| 2026-10-07 | 黄冈竹楼记 | 文件在「选修（2026起默写）」目录，`volume` 却写「选择性必修下册」 | 高考分组护栏 2.10 |

这四条有一个共同点：**构建全绿、校验全绿、链接全通、注音齐全，内容却是错的。**
所以流程里第 1 步要的是依据，不是「看起来对」。
