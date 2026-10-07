#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐册工作台：把台账按「册」摊开，用来核对教材位置。

为什么单独要这一份：台账按篇目排，看不出「某一册到底装了什么」。
册次错了，站点的按册浏览就会把课文挂到错误的课本上。

用法：
  python tools/build-textbook-table.py
产出：docs/textbook-contents.md（自动生成，不要手改）
"""
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / 'data' / 'ledger.json'

# 册次裁定记录：每一条都必须写清「依据什么」，不然就是拍脑袋。
RULINGS = [
    ('杜牧《赤壁》', '删除 poems/高中/必修下册/赤壁.md（保留七年级下册那份）',
     '高中课标 72 篇里没有杜牧《赤壁》（只有苏轼《赤壁赋》）；初中课标 22 有。两份原文完全相同，必有一份是多余的。'),
    ('王翰《凉州词》', '删除 poems/小学/五年级下册/凉州词.md（保留四年级上册那份）',
     '课标只列一次（小学 11「凉州（葡萄美酒夜光杯）」）。统编四年级上册有《古诗三首》含《凉州词》；'
     '五年级下册的《古诗三首》是《从军行》《秋夜将晓出篱门迎凉有感》《闻官军收河南河北》，没有《凉州词》。'),
    ('卢纶《塞下曲（月黑雁飞高）》', '删除 poems/小学/五年级下册/塞下曲.md（保留四年级下册那份）',
     '课标只列一次（小学 32）。统编四年级下册《古诗三首》含《塞下曲》（与《芙蓉楼送辛渐》《墨梅》同课）；'
     '五年级下册没有这篇。'),
    ('王勃《送杜少府之任蜀州》', '删除 poems/初中/七年级上册/送杜少府之任蜀州.md（保留八年级下册课外诵读那份）',
     '统编八年级下册第三单元「课外古诗词诵读」收这篇；七年级上、下册的课外古诗词诵读都不收。课标只列一次（初中 07）。'),
    ('韩愈《杂说（四）》', '删除 poems/初中/八年级下册/杂说.md；把 poems/初中/八年级下册/马说.md 补成全文，'
     '并在 data/title-aliases.json 登记「课标 杂说（四）= 仓内 马说」',
     '杂说.md 标题写韩愈《杂说（四）》，正文却是「是故无冥明之察」「善哉，答是」四句——'
     '既不是韩愈的文字，也不是《礼记·学记》的原文，属编排错误。韩愈《杂说》四则之四通称《马说》，'
     '统编八年级下册第 23 课即《马说》。'),
    ('佚名《虽有嘉肴》', '正文重写为统编教材原文，注释/译文/赏析随之重写，并加「异文」小节记录这次裁定',
     '旧版正文后四句「是故无冥明之察」「是故无经无纬」「是故无道无观」「善哉，答是」是编造出来的，'
     '《礼记·学记》原文作「是故学然后知不足，教然后知困……故曰：教学相长也」。'
     '这是本次核查里最严重的一处：一篇课标要求背诵的课文，正文是假的。'),
    ('《大道之行也》与《礼运》', '两份都保留，登记为「正常」',
     '同一段《礼记·礼运》，义务教育课标（初中）与高中课标各列一次，默写范围与学段不同；'
     '合并成一份会让「初中背诵范围」变含糊。'),
    ('竹里馆 / 春夜洛城闻笛 / 逢入京使 / 晚春', '册次由「七年级课外诵读」改为「七年级下册课外诵读」，目录同步改名',
     '「七年级课外诵读」看不出挂在哪一册。统编七年级下册课外古诗词诵读第一组正是这四首。'),
]

STAGE_ORDER = ['小学', '初中', '高中']
VOLUME_ORDER = {
    '小学': ['一年级上册', '一年级下册', '二年级上册', '二年级下册', '三年级上册', '三年级下册',
             '四年级上册', '四年级下册', '五年级上册', '五年级下册', '六年级上册', '六年级下册'],
    '初中': ['七年级上册', '七年级下册', '七年级下册课外诵读', '八年级上册', '八年级上册课外诵读',
             '八年级下册', '八年级下册课外诵读', '九年级上册', '九年级下册'],
    '高中': ['必修上册', '必修下册', '选择性必修上册', '选择性必修中册', '选择性必修下册', '选修（2026起默写）'],
}


def main():
    data = json.loads(LEDGER.read_text(encoding='utf-8'))
    rows = data['rows']
    summary = data['summary']

    by_vol = {}
    for r in rows:
        by_vol.setdefault((r['stage'], r['volume']), []).append(r)

    L = []
    L.append('# 逐册工作台（自动生成）')
    L.append('')
    L.append('> 由 `python tools/build-textbook-table.py` 生成于 %s。数据源是 data/ledger.json，'
             '台账又来自 poems/ 与两份课标契约。**不要手改本文件**。' % summary['generated'])
    L.append('')
    L.append('## 口径')
    L.append('')
    L.append('- 教材版本口径：**统编本为主**（小学 2024 修订、初中 2019、高中 2019 起用）。')
    L.append('- 正文只有一份，册次记的是「首次收录册次」；教材调整记在下面的裁定记录里，不按年份复制三套正文。')
    L.append('- 「课外诵读」指统编教材每册末尾的「课外古诗词诵读」栏目：教材要求诵读，但不是教读课文。')
    L.append('- 「选修（2026起默写）」是高中默写范围标记，不是教材册次：2025 届及以前默写 60 篇，'
             '2026 届起按新教材默写 72 篇，这 12 篇只在 2026 届起考。')
    L.append('')
    L.append('## 册次一致性护栏')
    L.append('')
    L.append('validate.py 会检查每篇的 `volume` 是否与其 `stage` 相配：小学只能是一~六年级上下册，'
             '初中只能是七~九年级上下册或某册的课外诵读，高中只能是必修/选择性必修的册。'
             '含糊写法（如「七年级课外诵读」）直接报错。')
    L.append('')
    L.append('## 核验状态（这一栏不许含糊）')
    L.append('')
    L.append('**已核到教材单元级**（有公开可查的教材目录或教研文献佐证）：')
    L.append('')
    L.append('- 九年级下册 第三单元：9《鱼我所欲也》、10《唐雎不辱使命》、11《送东阳马生序》、12《词四首》；第六单元：20《曹刿论战》、21《邹忌讽齐王纳谏》、22《陈涉世家》、23《出师表》、24《诗词曲五首》。')
    L.append('- 八年级下册 第三单元「课外古诗词诵读」收《送杜少府之任蜀州》。')
    L.append('- 五年级下册 第四单元《古诗三首》=《从军行》《秋夜将晓出篱门迎凉有感》《闻官军收河南河北》。')
    L.append('- 四年级上册、四年级下册各有《古诗三首》一课（四下那课含《塞下曲》）。')
    L.append('- 七年级下册 课外古诗词诵读第一组 =《竹里馆》《春夜洛城闻笛》《逢入京使》《晚春》。')
    L.append('')
    L.append('**未核到单元级**（只核到「学段正确」，具体册次沿用仓内既有标注）：')
    L.append('')
    L.append('- 小学 12 册里除上面几课之外的篇目；高中 五册的必修/选择性必修挂法。')
    L.append('- 初中最可疑的一处：仓内把《渔家傲·秋思》《江城子·密州出猎》《破阵子》《南乡子》挂在九年级上册，而统编九年级下册第 12 课《词四首》通常正是《渔家傲·秋思》《江城子·密州出猎》《破阵子·为陈同甫赋壮词以寄之》《满江红》。这一条**存疑**：要拿到教材目录逐册核对后再改，不许凭印象搬。')
    L.append('')
    L.append('存疑的册次只影响「按册浏览」把课文挂在哪一册，不影响正文、注释、译文与背诵范围。站点的按册浏览不得把它写成教材原话，要写成「本仓的整理口径」。')
    L.append('')
    L.append('## 册次裁定记录')
    L.append('')
    L.append('| 篇目 | 裁定 | 依据 |')
    L.append('|---|---|---|')
    for title, ruling, basis in RULINGS:
        L.append('| %s | %s | %s |' % (title, ruling, basis))
    L.append('')
    L.append('## 逐册一览')
    L.append('')
    for stage in STAGE_ORDER:
        L.append('### %s' % stage)
        L.append('')
        for vol in VOLUME_ORDER[stage]:
            items = sorted(by_vol.get((stage, vol)) or [],
                           key=lambda r: (r['syllabusNo'] if r['syllabusNo'] is not None else 999, r['id']))
            L.append('#### %s（%d 篇）' % (vol, len(items)))
            L.append('')
            if not items:
                L.append('_仓内这一册没有篇目。_')
                L.append('')
                continue
            L.append('| 课标 | 篇目 | 作者 | 体裁 | 背诵 | 归类 |')
            L.append('|---|---|---|---|---|---|')
            for r in items:
                no = ('%s %02d' % (r['syllabusGroup'], r['syllabusNo'])) if r['syllabusNo'] is not None else '—'
                L.append('| %s | %s | %s | %s | %s | %s |' % (
                    no, r['title'], r['author'], r['form'] or '', r['recite'] or '**缺**', r['category']))
            L.append('')
    (ROOT / 'docs' / 'textbook-contents.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    total = sum(len(v) for v in by_vol.values())
    print('已写 docs/textbook-contents.md：%d 册 / %d 篇' % (len(by_vol), total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
