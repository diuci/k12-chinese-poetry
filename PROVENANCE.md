# 来源与版权台账

本文件是全仓内容的**版权台账**。每一篇的详细来源同时记录在该篇的
frontmatter `source` 字段中；本表为汇总视图，由 `tools/validate.py`
与 `poems/` 内容交叉校验。

## 版权状态总览

| 类别 | 篇数 | 版权状态 | 依据 | 许可 |
|---|---|---|---|---|
| 古诗文原文（有署名作者） | 214 | 公有领域 | 作者卒年 ≤ 当前年 − 50，逐篇记 `authorDied` | 自由使用 |
| 作者不详的《诗经》、乐府、民歌等 | 39 | 公有领域 | 成书年代上限 `authorEraEnd` | 自由使用 |
| 注释 / 译文 / 赏析 | 253 | 我方原创 | 自行撰写，不摘抄商业站 | CC BY 4.0 |
| 选篇编排（取舍与顺序） | — | 我方原创 | — | CC BY 4.0 |
| 课标附录 1 清单 | 135 | 政府文件 | 教育部公开发布 | 整理版我方版权 |
| 仍在保护期内的现当代作品 | 0 收录 | 受保护 | 卒年 > 当前年 − 50 | 不收录，登记在 `pending/` |

**这条不是文档说法，是脚本在跑的规则**：`tools/validate.py` 第 8 项逐篇核验卒年，
不满足即构建失败；`--selftest` 用一个 1999 年卒的假作者验证它真的会拦。

> 2026-10-06 更正：本表此前把秋瑾《满江红·小住京华》列为「保护期内」，
> 又把「作者殁逾百年」当作依据。两处都不成立——秋瑾 1907 年逝世，按 50 年规则
> 1957 年底即已届满，属公有领域；而「逾百年」这种说法没法逐篇核验。
> 现在依据统一成一条：作者卒年 + 50 年保护期。详见 `pending/INDEX.md`。

## 来源代号

见 [docs/sources.md](docs/sources.md) 的完整说明。

| 代号 | 来源 | 许可 | 用途 |
|---|---|---|---|
| S1 | 义务教育语文课程标准（2022年版）附录1 | 政府文件 | 定 135 篇框架 |
| S2 | 人民教育出版社官网统编教材目录 | 版权 | 仅取册次元数据 |
| S3 | chinese-poetry（48.9k★） | **MIT** | 原文字句初稿 |
| S4 | chinese-poetry-npm | MIT | 分片 JSON 取用 |
| S5 | 古诗文网等商业站 | 版权 | 仅比对用字，不复制 |
| S6 | 各地教研整理清单 | 商业 | 仅交叉验证 |
| S7 | 中考真题（2024–2025） | — | 标注高频度 |

## 用字校订记录

以人教社统编教材为**用字准绳**。以下为已知的易错字，记录备查：

| 篇目 | 教材用字 | 常见误用 | 说明 |
|---|---|---|---|
| 小池 | 树**阴**照水 | 树荫 | 2017 年教材修订后统一为「树阴」 |
| 元日 | 曈**曈**日 | 瞳瞳 | 「曈」为日字旁，指太阳初升 |
| 六月二十七日望湖楼醉书 | 淡妆 | 浓妆 | 不同版本有异，教材用「淡妆」 |
| 咏柳 | 碧玉妆成 | 妆成一树高 | 语序以教材为准 |

> 发现新的用字差异时，请更新本表并在对应篇目的 frontmatter
> `source.verified_by` 中记录校订者。

## 逐篇台账

以前这张表是空的，却写着「由 validate.py 校验完整性」——空表校验空表，
比没有检查更危险。现在它从 `data/poems.json` 生成，改篇目就重新生成。

<!-- 逐篇台账：由 tools/gen-provenance.py 生成，勿手改 -->

> 本表由 `tools/gen-provenance.py` 从 `data/poems.json` 生成，共 272 篇。
> 改篇目后跑 `python tools/gen-provenance.py` 重新生成，不要手改这张表。
> 「公有领域证据」一列就是 `validate.py` 第 8 项核验的那个年份。

| id | 篇目 | 作者 | 朝代 | 公有领域证据 | 原文版权 | 来源 | 体裁 | 学段 · 册次 |
|---|---|---|---|---|---|---|---|---|
| lunyu12-cz | 《论语》十二章 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S9+S1+S2+S10 | 文言 | 初中 · 七年级上册 |
| shiyiyuesirifengyudazuo | 十一月四日风雨大作 | 陆游 | 宋 | 卒 1210 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级上册课外诵读 |
| yeshangshouxiangchengwendi | 夜上受降城闻笛 | 李益 | 唐 | 卒 829 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级上册课外诵读 |
| yeyujibei | 夜雨寄北 | 李商隐 | 唐 | 卒 858 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级上册 |
| tianjingsha-qiusi | 天净沙 | 马致远 | 元 | 卒 1321 | public-domain | S3+S1+S2 | 曲 | 初中 · 七年级上册 |
| shanpoyang | 山坡羊 | 张养浩 | 元 | 卒 1329 | public-domain | S3+S1+S2 | 曲 | 初中 · 九年级下册 |
| emeishanyuege | 峨眉山月歌 | 李白 | 唐 | 卒 762 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级上册课外诵读 |
| jihai-jimao | 己亥杂诗 | 龚自珍 | 清 | 卒 1841 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级下册 |
| wuti | 无题 | 李商隐 | 唐 | 卒 858 | public-domain | S3+S1+S2 | 七言 | 初中 · 九年级上册 |
| chunyeluocheng | 春夜洛城闻笛 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级下册课外诵读 |
| wanchun | 晚春 | 韩愈 | 唐 | 卒 824 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级下册课外诵读 |
| wangyue | 望岳 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 五言 | 初中 · 七年级下册 |
| mulanci | 木兰辞 | 佚名 | 北朝 | 年代上限 1900 | public-domain | S3+S1+S2 | 乐府 | 初中 · 七年级下册 |
| cibeigushanxia | 次北固山下 | 王湾 | 唐 | 卒 751 | public-domain | S3+S1+S2 | 五言 | 初中 · 七年级上册 |
| shuidiaogetou | 水调歌头 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 词 | 初中 · 九年级上册 |
| jiangnanfengligunian | 江南逢李龟年 | 杜甫 | 唐 | 卒 770 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级上册课外诵读 |
| boqinhuai | 泊秦淮 | 杜牧 | 唐 | 卒 852 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级下册 |
| youshanxincun | 游山西村 | 陆游 | 宋 | 卒 1210 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级下册 |
| tongguan | 潼关 | 谭嗣同 | 清 | 卒 1898 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级上册课外诵读 |
| ailianshuo | 爱莲说 | 周敦颐 | 宋 | 卒 1073 | public-domain | S3+S1+S2 | 文言 | 初中 · 七年级下册 |
| dengyouzhoutai | 登幽州台歌 | 陈子昂 | 唐 | 卒 702 | public-domain | S3+S1+S2 | 杂言 | 初中 · 七年级下册 |
| dengfeilaifeng | 登飞来峰 | 王安石 | 宋 | 卒 1086 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级下册 |
| xiangjianhuan | 相见欢 | 李煜 | 南唐 | 卒 978 | public-domain | S3+S1+S2 | 词 | 初中 · 九年级上册 |
| qiuci | 秋词 | 刘禹锡 | 唐 | 卒 842 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级上册课外诵读 |
| zhuliguan | 竹里馆 | 王维 | 唐 | 卒 761 | public-domain | S3+S1+S2 | 五言 | 初中 · 七年级下册课外诵读 |
| yueke | 约客 | 赵师秀 | 宋 | 卒 1220 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级下册课外诵读 |
| xingjunjiuri | 行军九日思长安故园 | 岑参 | 唐 | 卒 770 | public-domain | S10+S9+S3 | 五言 | 初中 · 七年级上册课外诵读 |
| xinglunan | 行路难 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 杂言 | 初中 · 九年级上册 |
| guancanghai | 观沧海 | 曹操 | 汉 | 卒 220 | public-domain | S3+S1+S2 | 乐府 | 初中 · 七年级上册 |
| jiasheng | 贾生 | 李商隐 | 唐 | 卒 858 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级下册课外诵读 |
| guosongyuan | 过松源晨炊漆公店 | 杨万里 | 宋 | 卒 1206 | public-domain | S10+S9+S3 | 七言 | 初中 · 七年级下册课外诵读 |
| guolingyang | 过零丁洋 | 文天祥 | 宋 | 卒 1283 | public-domain | S3+S1+S2 | 七言 | 初中 · 九年级下册 |
| fengrujinshi | 逢入京使 | 岑参 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级下册课外诵读 |
| wenwangchangling | 闻王昌龄左迁龙标遥有此寄 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 七言 | 初中 · 七年级上册 |
| loushiming | 陋室铭 | 刘禹锡 | 唐 | 卒 842 | public-domain | S3+S1+S2 | 文言 | 初中 · 七年级下册 |
| sanxia | 三峡 | 郦道元 | 北魏 | 卒 527 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级上册 |
| yuzhusianshu | 与朱元思书 | 吴均 | 南朝 | 卒 520 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级上册 |
| shizhuisai | 使至塞上 | 王维 | 唐 | 卒 761 | public-domain | S3+S1+S2 | 五言 | 初中 · 八年级上册 |
| guanju | 关雎 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 诗经 | 初中 · 八年级下册 |
| beimingyouyu | 北冥有鱼 | 庄子 | 战国 | 卒 公元前 286 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级下册 |
| maotanshangwu | 卖炭翁 | 白居易 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 七言 | 初中 · 八年级下册 |
| dadaozhixing | 大道之行也 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级下册 |
| rumengling | 如梦令 | 李清照 | 宋 | 卒 1155 | public-domain | S10+S9+S3 | 词 | 初中 · 八年级上册课外诵读 |
| zijin | 子衿 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 诗经 | 初中 · 八年级下册课外诵读 |
| xiaoshitan | 小石潭记 | 柳宗元 | 唐 | 卒 819 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级下册 |
| tingzhongyouqishu | 庭中有奇树 | 佚名 | 汉 | 年代上限 1900 | public-domain | S10+S9+S3 | 古诗 | 初中 · 八年级上册课外诵读 |
| shiwei | 式微 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 诗经 | 初中 · 八年级下册课外诵读 |
| chunwang | 春望 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 五言 | 初中 · 八年级上册 |
| taohuayuanji | 桃花源记 | 陶潜 | 晋 | 卒 427 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级下册 |
| liangfuxing | 梁甫行 | 曹植 | 汉 | 卒 232 | public-domain | S10+S9+S3 | 五言 | 初中 · 八年级上册课外诵读 |
| huanxisha-yanque | 浣溪沙 | 晏殊 | 宋 | 卒 1055 | public-domain | S3+S1+S2 | 词 | 初中 · 八年级上册 |
| yujiaao-tianjie | 渔家傲 | 李清照 | 宋 | 卒 1155 | public-domain | S1+S2+S9 | 词 | 初中 · 八年级上册课外诵读 |
| dujingmensongbie | 渡荆门送别 | 李白 | 唐 | 卒 762 | public-domain | S10+S9+S3 | 五言 | 初中 · 八年级上册课外诵读 |
| shihaoli | 石壕吏 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级下册 |
| daxiezhongshu | 答谢中书书 | 陶弘景 | 南朝 | 卒 536 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级上册 |
| maowu | 茅屋为秋风所破歌 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 杂言 | 初中 · 八年级下册 |
| jianjia | 蒹葭 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 诗经 | 初中 · 八年级下册 |
| suoyoujiayao | 虽有嘉肴 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级下册 |
| jichengtiansi | 记承天寺夜游 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级上册 |
| zengcongdi | 赠从弟 | 刘桢 | 汉 | 卒 217 | public-domain | S10+S9+S3 | 五言 | 初中 · 八年级上册课外诵读 |
| chibi-du | 赤壁 | 杜牧 | 唐 | 卒 852 | public-domain | S3+S1+S2 | 七言 | 初中 · 八年级上册 |
| songshaoshu-wai | 送杜少府之任蜀州 | 王勃 | 唐 | 卒 676 | public-domain | S3+S1+S2 | 五言 | 初中 · 八年级下册课外诵读 |
| caisangzi | 采桑子 | 欧阳修 | 宋 | 卒 1072 | public-domain | S10+S9+S3 | 词 | 初中 · 八年级上册课外诵读 |
| yewang | 野望 | 王绩 | 唐 | 卒 644 | public-domain | S3+S1+S2 | 五言 | 初中 · 八年级上册课外诵读 |
| qiantanghuchunxing | 钱塘湖春行 | 白居易 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 七言 | 初中 · 八年级上册 |
| yanmenshiweixing | 雁门太守行 | 李贺 | 唐 | 卒 816 | public-domain | S3+S1+S2 | 七言 | 初中 · 八年级上册 |
| yinjiujiusan | 饮酒 | 陶潜 | 晋 | 卒 427 | public-domain | S3+S1+S2 | 五言 | 初中 · 八年级上册 |
| masuo | 马说 | 韩愈 | 唐 | 卒 824 | public-domain | S3+S1+S2 | 文言 | 初中 · 八年级下册 |
| huanghelou-cuiheng | 黄鹤楼 | 崔颢 | 唐 | 卒 754 | public-domain | S3+S1+S2 | 七言 | 初中 · 八年级上册 |
| guisuishou | 龟虽寿 | 曹操 | 汉 | 卒 220 | public-domain | S10+S9+S3 | 四言 | 初中 · 八年级上册课外诵读 |
| lvshi1 | 《吕氏春秋》一则 | 佚名 | 战国 | 年代上限 1900 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级下册 |
| mengzi3 | 《孟子》三则 | 孟子 | 战国 | 卒 公元前 289 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级下册 |
| zhuangzi1 | 《庄子》一则 | 庄子 | 战国 | 卒 公元前 286 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级下册 |
| liji1 | 《礼记》一则 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级下册 |
| chushibiao | 出师表 | 诸葛亮 | 三国 | 卒 234 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级下册 |
| bieyunjian | 别云间 | 夏完淳 | 明 | 卒 1647 | public-domain | S10+S9+S3 | 五言 | 初中 · 九年级下册课外诵读 |
| shiwucongjunzheng | 十五从军征 | 佚名 | 汉 | 年代上限 220 | public-domain | S1+S2+S3 | 乐府 | 初中 · 九年级下册 |
| nangxiangzi | 南乡子 | 辛弃疾 | 宋 | 卒 1207 | public-domain | S3+S1+S2 | 词 | 初中 · 九年级下册 |
| xianyangchengdonglou | 咸阳城东楼 | 许浑 | 唐 | 卒 858 | public-domain | S10+S9+S3 | 七言 | 初中 · 九年级上册课外诵读 |
| yueyanglouji | 岳阳楼记 | 范仲淹 | 宋 | 卒 1052 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级上册 |
| caoguilunzhan | 曹刿论战 | 左丘明 | 先秦 | 卒 公元前 422 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级下册 |
| chaotianzi | 朝天子·咏喇叭 | 王磐 | 明 | 年代上限 1530 | public-domain | S3+S1b+S2 | 曲 | 初中 · 九年级下册 |
| jiangchengzi-laofeng | 江城子 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 词 | 初中 · 九年级下册 |
| yujiaao-qiusi | 渔家傲 | 范仲淹 | 宋 | 卒 1052 | public-domain | S3+S1+S2 | 词 | 初中 · 九年级下册 |
| huxinting | 湖心亭看雪 | 张岱 | 明 | 卒 1679 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级上册 |
| manjianghong-xiaozhujinghua | 满江红 | 秋瑾 | 清 | 卒 1907 | public-domain | S1+S2+S9 | 词 | 初中 · 九年级下册 |
| baixuege | 白雪歌送武判官归京 | 岑参 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 七言 | 初中 · 九年级下册 |
| pozhenzi | 破阵子 | 辛弃疾 | 宋 | 卒 1207 | public-domain | S3+S1+S2 | 词 | 初中 · 九年级下册 |
| songdongyang | 送东阳马生序 | 宋濂 | 明 | 卒 1381 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级下册 |
| zouji | 邹忌讽齐王纳谏 | 佚名 | 战国 | 年代上限 1900 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级下册 |
| choulitian | 酬乐天扬州初逢席上见赠 | 刘禹锡 | 唐 | 卒 842 | public-domain | S3+S1+S2 | 七言 | 初中 · 九年级上册 |
| zuigongtingji | 醉翁亭记 | 欧阳修 | 宋 | 卒 1072 | public-domain | S3+S1+S2 | 文言 | 初中 · 九年级上册 |
| changshaguojiayizhai | 长沙过贾谊宅 | 刘长卿 | 唐 | 卒 790 | public-domain | S10+S9+S3 | 七言 | 初中 · 九年级上册课外诵读 |
| gulangyuexing | 古朗月行 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级上册 |
| yonge | 咏鹅 | 骆宾王 | 唐 | 卒 684 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级上册 |
| xunyinzhe | 寻隐者不遇 | 贾岛 | 唐 | 卒 843 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级下册 |
| xiaochi | 小池 | 杨万里 | 宋 | 卒 1206 | public-domain | S3+S1+S2 | 七言 | 小学 · 一年级下册 |
| minnong2 | 悯农其二 | 李绅 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级上册 |
| chunxiao | 春晓 | 孟浩然 | 唐 | 卒 740 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级下册 |
| jiangnan | 江南 | 汉乐府 | 汉 | 年代上限 220 | public-domain | S3+S1+S2 | 杂言 | 小学 · 一年级上册 |
| chishang | 池上 | 白居易 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级下册 |
| hua | 画 | 佚名 | 唐 | 年代上限 1900 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级上册 |
| huaji | 画鸡 | 唐寅 | 明 | 卒 1524 | public-domain | S3+S1+S2 | 七言 | 小学 · 一年级下册 |
| xiangsi | 相思 | 王维 | 唐 | 卒 761 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级下册 |
| zengwanglun | 赠汪伦 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 七言 | 小学 · 一年级下册 |
| jingyesi | 静夜思 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级下册 |
| feng | 风 | 李峤 | 唐 | 卒 719 | public-domain | S3+S1+S2 | 五言 | 小学 · 一年级上册 |
| yongliu | 咏柳 | 贺知章 | 唐 | 卒 744 | public-domain | S3+S1+S2 | 七言 | 小学 · 二年级下册 |
| yesushansi | 夜宿山寺 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 五言 | 小学 · 二年级上册 |
| xiaoerchuidiao | 小儿垂钓 | 胡令能 | 唐 | 卒 805 | public-domain | S3+S1+S2 | 七言 | 小学 · 二年级上册 |
| minnong1 | 悯农其一 | 李绅 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 五言 | 小学 · 二年级下册 |
| chilege | 敕勒歌 | 北朝民歌 | 南北朝 | 年代上限 560 | public-domain | S3+S1+S2 | 杂言 | 小学 · 二年级上册 |
| jingcisi | 晓出净慈寺送林子方 | 杨万里 | 宋 | 卒 1206 | public-domain | S3+S1+S2 | 七言 | 小学 · 二年级下册 |
| wanglushanpubu | 望庐山瀑布 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 七言 | 小学 · 二年级上册 |
| cunju | 村居 | 高鼎 | 清 | 年代上限 1900 | public-domain | S3+S1+S2 | 七言 | 小学 · 二年级下册 |
| meihua | 梅花 | 王安石 | 宋 | 卒 1086 | public-domain | S3+S1+S2 | 五言 | 小学 · 二年级上册 |
| jiangxue | 江雪 | 柳宗元 | 唐 | 卒 819 | public-domain | S3+S1+S2 | 五言 | 小学 · 二年级上册 |
| dengguanquelou | 登鹳雀楼 | 王之涣 | 唐 | 卒 742 | public-domain | S3+S1+S2 | 五言 | 小学 · 二年级上册 |
| jueju-huangli | 绝句 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 七言 | 小学 · 二年级下册 |
| zhouyeshujian | 舟夜书所见 | 查慎行 | 清 | 卒 1721 | public-domain | S3+S1+S2 | 五言 | 小学 · 二年级下册 |
| guyuancao | 赋得古原草送别 | 白居易 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 五言 | 小学 · 二年级下册 |
| sanqudaozhong | 三衢道中 | 曾几 | 宋 | 卒 1166 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级下册 |
| jiuyuejiuri | 九月九日忆山东兄弟 | 王维 | 唐 | 卒 761 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级下册 |
| yuanri | 元日 | 王安石 | 宋 | 卒 1086 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级下册 |
| yeshusuojian | 夜书所见 | 叶绍翁 | 宋 | 年代上限 1270 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级上册 |
| dalinsitaohua | 大林寺桃花 | 白居易 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级下册 |
| shanxing | 山行 | 杜牧 | 唐 | 卒 852 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级上册 |
| yijiangnan | 忆江南 | 白居易 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 词 | 小学 · 三年级下册 |
| huichongchunjiang | 惠崇春江晚景 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级下册 |
| suojian | 所见 | 袁枚 | 清 | 卒 1797 | public-domain | S3+S1+S2 | 五言 | 小学 · 三年级上册 |
| zaofabaidicheng | 早发白帝城 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级上册 |
| wangtianmenshan | 望天门山 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级上册 |
| wangdongting | 望洞庭 | 刘禹锡 | 唐 | 卒 842 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级上册 |
| qingming | 清明 | 杜牧 | 唐 | 卒 852 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级下册 |
| chuzhouxijian | 滁州西涧 | 韦应物 | 唐 | 卒 792 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级下册 |
| jueju-chiri | 绝句 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 五言 | 小学 · 三年级下册 |
| zengliujingwen | 赠刘景文 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级上册 |
| cailianqu | 采莲曲 | 王昌龄 | 唐 | 卒 757 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级上册 |
| yinhushang | 饮湖上初晴后雨 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 七言 | 小学 · 三年级上册 |
| liangzhouci-wanghan | 凉州词 | 王翰 | 唐 | 卒 726 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级上册 |
| chusai | 出塞 | 王昌龄 | 唐 | 卒 757 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级上册 |
| biedongda | 别董大 | 高适 | 唐 | 卒 765 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级上册 |
| sishitianyuan-25 | 四时田园杂兴 | 范成大 | 宋 | 卒 1193 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级下册 |
| saixiaqu | 塞下曲 | 卢纶 | 唐 | 卒 780 | public-domain | S3+S1+S2 | 五言 | 小学 · 四年级下册 |
| momei | 墨梅 | 王冕 | 元 | 卒 1359 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级下册 |
| xiarijueju | 夏日绝句 | 李清照 | 宋 | 卒 1155 | public-domain | S3+S1+S2 | 五言 | 小学 · 四年级上册 |
| change | 嫦娥 | 李商隐 | 唐 | 卒 858 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级上册 |
| suxinshi | 宿新市徐公店 | 杨万里 | 宋 | 卒 1206 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级下册 |
| mujiangyin | 暮江吟 | 白居易 | 唐 | 卒 846 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级上册 |
| jiangpan | 江畔独步寻花 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级下册 |
| qingpingyue-cunju | 清平乐 | 辛弃疾 | 宋 | 卒 1207 | public-domain | S3+S1+S2 | 词 | 小学 · 四年级下册 |
| duzuojingting | 独坐敬亭山 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 五言 | 小学 · 四年级下册 |
| furonglou | 芙蓉楼送辛渐 | 王昌龄 | 唐 | 卒 757 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级下册 |
| feng-mi | 蜂 | 罗隐 | 唐 | 卒 909 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级下册 |
| xuemei | 雪梅 | 卢梅坡 | 宋 | 年代上限 1300 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级上册 |
| longpo | 题西林壁 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 七言 | 小学 · 四年级上册 |
| luchai | 鹿柴 | 王维 | 唐 | 卒 761 | public-domain | S3+S1+S2 | 五言 | 小学 · 四年级上册 |
| qiqiao | 乞巧 | 林杰 | 唐 | 年代上限 900 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级上册 |
| xiangcunsiyue | 乡村四月 | 翁卷 | 宋 | 年代上限 1225 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级下册 |
| congjunxing | 从军行 | 王昌龄 | 唐 | 卒 757 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级下册 |
| liangzhouci-wangzhihuan | 凉州词 | 王之涣 | 唐 | 卒 742 | public-domain | S1+S2+S9 | 七言 | 小学 · 五年级下册 |
| sishitianyuan-31 | 四时田园杂兴 | 范成大 | 宋 | 卒 1193 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级下册 |
| shanjuqiuming | 山居秋暝 | 王维 | 唐 | 卒 761 | public-domain | S3+S1+S2 | 五言 | 小学 · 五年级上册 |
| jihai | 己亥杂诗 | 龚自珍 | 清 | 卒 1841 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级上册 |
| cunwan | 村晚 | 雷震 | 宋 | 年代上限 1300 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级下册 |
| fengqiaoyebo | 枫桥夜泊 | 张继 | 唐 | 年代上限 800 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级上册 |
| yugezi | 渔歌子 | 张志和 | 唐 | 卒 810 | public-domain | S3+S1+S2 | 词 | 小学 · 五年级上册 |
| youziyin | 游子吟 | 孟郊 | 唐 | 卒 814 | public-domain | S3+S1+S2 | 六言 | 小学 · 五年级下册 |
| shier | 示儿 | 陆游 | 宋 | 卒 1210 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级上册 |
| qiuyejiangxiao | 秋夜将晓出篱门迎凉有感 | 陆游 | 宋 | 卒 1210 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级下册 |
| zhizibing | 稚子弄冰 | 杨万里 | 宋 | 卒 1206 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级下册 |
| guanshu | 观书有感 | 朱熹 | 宋 | 卒 1200 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级上册 |
| changxiangsi | 长相思 | 纳兰性德 | 清 | 卒 1685 | public-domain | S3+S1+S2 | 词 | 小学 · 五年级上册 |
| wenguanjun | 闻官军收河南河北 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级下册 |
| tilinandi | 题临安邸 | 林升 | 宋 | 年代上限 1300 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级上册 |
| niaomingjian | 鸟鸣涧 | 王维 | 唐 | 卒 761 | public-domain | S3+S1+S2 | 五言 | 小学 · 五年级下册 |
| huanghelou | 黄鹤楼送孟浩然之广陵 | 李白 | 唐 | 卒 762 | public-domain | S3+S1+S2 | 七言 | 小学 · 五年级下册 |
| shuhuyin | 书湖阴先生壁 | 王安石 | 宋 | 卒 1086 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级上册 |
| wanghulou | 六月二十七日望湖楼醉书 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级上册 |
| shiyiwangyue | 十五夜望月 | 王建 | 唐 | 卒 830 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级下册 |
| bosuanzi-song | 卜算子 | 王观 | 宋 | 年代上限 1150 | public-domain | S3+S1+S2 | 词 | 小学 · 六年级下册 |
| huixiangyoushu | 回乡偶书 | 贺知章 | 唐 | 卒 744 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级上册 |
| sujiandejiang | 宿建德江 | 孟浩然 | 唐 | 卒 740 | public-domain | S3+S1+S2 | 五言 | 小学 · 六年级上册 |
| hanshi | 寒食 | 韩翃 | 唐 | 卒 788 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级下册 |
| zaochun | 早春呈水部张十八员外 | 韩愈 | 唐 | 卒 824 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级下册 |
| chunyexiyu | 春夜喜雨 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1+S2 | 五言 | 小学 · 六年级下册 |
| chunri | 春日 | 朱熹 | 宋 | 卒 1200 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级上册 |
| jiangshangyuzhe | 江上渔者 | 范仲淹 | 宋 | 卒 1052 | public-domain | S3+S1+S2 | 五言 | 小学 · 六年级下册 |
| jiangnanchun | 江南春 | 杜牧 | 唐 | 卒 852 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级上册 |
| bochuanguazhou | 泊船瓜洲 | 王安石 | 宋 | 卒 1086 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级下册 |
| huanxisha-qishui | 浣溪沙 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1+S2 | 词 | 小学 · 六年级下册 |
| langtaosha | 浪淘沙 | 刘禹锡 | 唐 | 卒 842 | public-domain | S3+S1+S2 | 词 | 小学 · 六年级上册 |
| youyuanbuzhi | 游园不值 | 叶绍翁 | 宋 | 年代上限 1270 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级下册 |
| shihuiyin | 石灰吟 | 于谦 | 明 | 卒 1457 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级下册 |
| zhushi | 竹石 | 郑燮 | 清 | 卒 1765 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级下册 |
| xijiangyue | 西江月 | 辛弃疾 | 宋 | 卒 1207 | public-domain | S3+S1+S2 | 词 | 小学 · 六年级上册 |
| guogurenzhuang | 过故人庄 | 孟浩然 | 唐 | 卒 740 | public-domain | S3+S1+S2 | 五言 | 小学 · 六年级上册 |
| tiaotiaoqianniuxing | 迢迢牵牛星 | 佚名 | 汉 | 年代上限 1900 | public-domain | S3+S1+S2 | 五言 | 小学 · 六年级下册 |
| songyuaner | 送元二使安西 | 王维 | 唐 | 卒 761 | public-domain | S3+S1+S2 | 七言 | 小学 · 六年级下册 |
| caiwei | 采薇 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 四言 | 小学 · 六年级下册 |
| zengwang | 长歌行 | 汉乐府 | 汉 | 年代上限 220 | public-domain | S3+S1+S2 | 杂言 | 小学 · 六年级下册 |
| mashi | 马诗 | 李贺 | 唐 | 卒 816 | public-domain | S3+S1+S2 | 五言 | 小学 · 六年级下册 |
| mengziyize | 《孟子》一则 | 孟子 | 战国 | 卒 公元前 289 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选修（2026起默写） |
| laozi8 | 《老子》八章 | 老子 | 先秦 | 卒 公元前 470 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修上册 |
| lunyu12 | 《论语》十二章 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S9+S1b+S2+S10 | 文言 | 高中 · 选择性必修上册 |
| shangshumihan | 上枢密韩太尉书 | 苏辙 | 宋 | 卒 1112 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选修（2026起默写） |
| zhongyong | 中庸 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选修（2026起默写） |
| linanchunyu | 临安春雨初霁 | 陆游 | 宋 | 卒 1210 | public-domain | S3+S1b+S2 | 七言 | 高中 · 选择性必修下册 |
| shufen | 书愤 | 陆游 | 宋 | 卒 1210 | public-domain | S3+S1b+S2 | 七言 | 高中 · 选择性必修中册 |
| wudailingguan | 五代史伶官传序 | 欧阳修 | 宋 | 卒 1072 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修中册 |
| liuguolun | 六国论 | 苏洵 | 宋 | 卒 1066 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修下册 |
| lantingjixu | 兰亭集序 | 王羲之 | 晋 | 卒 361 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修下册 |
| quanxue | 劝学 | 荀子 | 战国 | 卒 公元前 238 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修上册 |
| gudaishilun | 古代文论选段 | 佚名 | 先秦 | 年代上限 1927 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选修（2026起默写） |
| shengshenman | 声声慢 | 李清照 | 宋 | 卒 1155 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修上册 |
| daxue | 大学 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修上册 |
| zilu-shizhe | 子路、曾皙、冉有、公西华侍坐 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修下册 |
| jishi-jiangfanjueyu | 季氏将伐颛臾 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选修（2026起默写） |
| kezhi | 客至 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1b+S2 | 七言 | 高中 · 选择性必修下册 |
| jiangjinjiu | 将进酒 | 李白 | 唐 | 卒 762 | public-domain | S3+S1b+S2 | 乐府 | 高中 · 选择性必修上册 |
| quyuanliezhuan | 屈原列传 | 司马迁 | 西汉 | 卒 公元前 86 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修中册 |
| shishuo | 师说 | 韩愈 | 唐 | 卒 824 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修上册 |
| guiqulaixici | 归去来兮辞 | 陶潜 | 晋 | 卒 427 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修下册 |
| guiyuantianju | 归园田居 | 陶潜 | 晋 | 卒 427 | public-domain | S3+S1b+S2 | 五言 | 高中 · 必修上册 |
| niannujiao-chibi | 念奴娇·赤壁怀古 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修上册 |
| niannujiao-gudong | 念奴娇·过洞庭 | 张孝祥 | 宋 | 卒 1170 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修下册 |
| yangzhousman | 扬州慢 | 姜夔 | 宋 | 卒 1221 | public-domain | S3+S1b+S2 | 词 | 高中 · 选择性必修下册 |
| baoranan | 报任安书 | 司马迁 | 西汉 | 卒 公元前 86 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修中册 |
| niluonan | 拟行路难 | 鲍照 | 南朝宋 | 卒 466 | public-domain | S3+S1b+S2 | 杂言 | 高中 · 选择性必修下册 |
| wuyi | 无衣 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 诗经 | 高中 · 选择性必修上册 |
| chunjianghuayue | 春江花月夜 | 张若虚 | 唐 | 卒 720 | public-domain | S3+S1b+S2 | 七言 | 高中 · 选择性必修上册 |
| wanghaichao | 望海潮 | 柳永 | 宋 | 卒 1053 | public-domain | S3+S1b+S2+S10 | 词 | 高中 · 选择性必修下册 |
| lipeng | 李凭箜篌引 | 李贺 | 唐 | 卒 816 | public-domain | S3+S1b+S2 | 七言 | 高中 · 选择性必修中册 |
| guizhixiang | 桂枝香·金陵怀古 | 王安石 | 宋 | 卒 1086 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修下册 |
| mengyoutianmu | 梦游天姥吟留别 | 李白 | 唐 | 卒 762 | public-domain | S3+S1b+S2 | 乐府 | 高中 · 必修上册 |
| yongyule | 永遇乐·京口北固亭怀古 | 辛弃疾 | 宋 | 卒 1207 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修上册 |
| jiangchengzi-yimao | 江城子 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1b+S2 | 词 | 高中 · 选择性必修上册 |
| shejiang | 涉江采芙蓉 | 佚名 | 汉 | 年代上限 1900 | public-domain | S3+S1b+S2 | 古诗 | 高中 · 必修上册 |
| tengwanggexu | 滕王阁序 | 王勃 | 唐 | 卒 676 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选修（2026起默写） |
| yange-xing | 燕歌行 | 高适 | 唐 | 卒 765 | public-domain | S3+S1b+S2 | 乐府 | 高中 · 选择性必修中册 |
| pipaxing | 琵琶行 | 白居易 | 唐 | 卒 846 | public-domain | S3+S1b+S2 | 乐府 | 高中 · 必修上册 |
| dengyueyanglou | 登岳阳楼 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1b+S2 | 五言 | 高中 · 必修下册 |
| dengkuai-ge | 登快阁 | 黄庭坚 | 宋 | 卒 1105 | public-domain | S3+S1b+S2 | 七言 | 高中 · 选择性必修下册 |
| dengtaishan | 登泰山记 | 姚鼐 | 清 | 卒 1815 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修上册 |
| denggao | 登高 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1b+S2 | 七言 | 高中 · 必修上册 |
| duange | 短歌行 | 曹操 | 汉 | 卒 220 | public-domain | S3+S1b+S2 | 乐府 | 高中 · 必修上册 |
| shizhongshan | 石钟山记 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修下册 |
| liyun | 礼运 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修上册 |
| lisao | 离骚 | 屈原 | 战国 | 卒 公元前 278 | public-domain | S3+S1b+S2 | 骚体 | 高中 · 选择性必修下册 |
| zhongshu-guotuotuo | 种树郭橐驼传 | 柳宗元 | 唐 | 卒 819 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修下册 |
| dasijianyishu | 答司马谏议书 | 王安石 | 宋 | 卒 1086 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修下册 |
| sumuzhe | 苏幕遮 | 周邦彦 | 宋 | 卒 1121 | public-domain | S3+S1b+S2 | 词 | 高中 · 选择性必修下册 |
| pusaman-wentingyun | 菩萨蛮 | 温庭筠 | 唐 | 卒 866 | public-domain | S3+S1b+S2 | 词 | 高中 · 选择性必修下册 |
| pusaman-zaoxiang | 菩萨蛮·书江西造口壁 | 辛弃疾 | 宋 | 卒 1207 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修上册 |
| yumeiren | 虞美人 | 李煜 | 南唐 | 卒 978 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修上册 |
| shuxiang | 蜀相 | 杜甫 | 唐 | 卒 770 | public-domain | S3+S1b+S2 | 七言 | 高中 · 选择性必修下册 |
| shudaonan | 蜀道难 | 李白 | 唐 | 卒 762 | public-domain | S3+S1b+S2 | 乐府 | 高中 · 选择性必修下册 |
| jiantaishisi | 谏太宗十思疏 | 魏征 | 唐 | 卒 643 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修下册 |
| jianzhukeshu | 谏逐客书 | 李斯 | 秦 | 卒 公元前 208 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修下册 |
| hexinlao | 贺新郎 | 刘克庄 | 宋 | 卒 1269 | public-domain | S3+S1b+S2 | 词 | 高中 · 选择性必修下册 |
| chibifu | 赤壁赋 | 苏轼 | 宋 | 卒 1101 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修上册 |
| guoqinlun | 过秦论 | 贾谊 | 西汉 | 卒 公元前 168 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修中册 |
| xiaoyaoyou | 逍遥游 | 庄子 | 战国 | 卒 公元前 286 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选修（2026起默写） |
| jinse | 锦瑟 | 李商隐 | 唐 | 卒 858 | public-domain | S3+S1b+S2 | 七言 | 高中 · 选择性必修中册 |
| changting-songbei | 长亭送别 | 王实甫 | 元 | 年代上限 1340 | public-domain | S3+S1b+S2 | 曲 | 高中 · 选择性必修下册 |
| epenggongfu | 阿房宫赋 | 杜牧 | 唐 | 卒 852 | public-domain | S3+S1b+S2 | 文言 | 高中 · 必修下册 |
| chenqingbiao | 陈情表 | 李密 | 晋 | 卒 287 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修下册 |
| qingyu-an | 青玉案·元夕 | 辛弃疾 | 宋 | 卒 1207 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修上册 |
| jingnv | 静女 | 佚名 | 先秦 | 年代上限 1900 | public-domain | S3+S1+S2 | 诗经 | 高中 · 必修上册 |
| xiangjixuanzhi | 项脊轩志 | 归有光 | 明 | 卒 1571 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选择性必修下册 |
| qiqiaoxian | 鹊桥仙 | 秦观 | 宋 | 卒 1100 | public-domain | S3+S1b+S2 | 词 | 高中 · 必修上册 |
| huanggangzhulouji | 黄冈竹楼记 | 王禹偁 | 宋 | 卒 1001 | public-domain | S3+S1b+S2 | 文言 | 高中 · 选修（2026起默写） |

<!-- 台账结束 -->

## 公有领域论证

我国《著作权法》：自然人作品的保护期为作者终生及其死亡后**第五十年的 12 月 31 日**。
所以判定式只有一条——**作者卒年 ≤ 当前年 − 50**。

本仓 253 篇的卒年证据全部存在篇目 frontmatter（`authorDied`，公元前为负数；
佚名、汉乐府、北朝民歌用 `authorEraEnd` 记年代上限），作者总表见
[`data/authors.json`](data/authors.json)（108 位作者）。

本仓**最晚的卒年**是清代（姚鼐 1815、龚自珍 1841），距 50 年保护期还有百年以上余量；
佚名类作品的年代上限最晚为 1900，同样远在保护期外。

仍在保护期内的现当代作家（例如冰心，1999 年卒，保护期至 2049-12-31）**不收录原文**，
登记在 `pending/INDEX.md`。

## 侵权通知

认为本仓某处侵犯了你的权利，请联系 **hi@diuci.com**，写明具体篇目与依据；
我们核实后下架、更正或取得授权。