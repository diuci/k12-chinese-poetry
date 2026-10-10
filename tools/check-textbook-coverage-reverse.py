#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反向核对：统编教材收了、仓里对不上的课文，列成一张表。

先前只有正向核对（仓里每一篇去教材目录里找）。反向没人数过：教材收了、仓里没有，
这一类缺口当时是看不见的。这张表不判「该不该收」——它只把缺口数出来、写明是按什么对的、
哪些一眼就不是仓的口径（现代文课文），剩下的逐条要人裁定。"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / 'data' / 'textbook-lessons.json'
POEMS = ROOT / 'data' / 'poems.json'
OUT_MD = ROOT / 'docs' / 'textbook-gaps.md'
OUT_JSON = ROOT / 'data' / 'textbook-gaps.json'

SEP = re.compile(r'[\s《》""“”‘’、，。·•・()（）*＊]')
# 一眼不属于仓的口径（现当代课文、单元导语、栏目）。这一档只用于「少报噪音」，不用于「不收」。
MODERN = re.compile(r'(课文|口语|综合性|写作|专题|活动|阅读|名著|单元|名著导读|快乐读书吧|思考|探究|研讨|演讲|新闻|通讯|报告|回忆|散文|小说|戏剧|纪念|怀念|母亲|先生|园林|桥|瀑布|雪山|草原|土地|海燕|故乡|叔叔|于勒|大观园|孔乙己|变色龙|溜索|蒲柳|枣儿|天下第一楼|社戏|回延安|安塞腰鼓|灯笼|灯笼|语言|恐龙|沙子|脚印|核舟|讲演|抉择|复兴|奥林匹克)')


def norm(s):
    return SEP.sub('', str(s or ''))


def load_poem_keys():
    poems = json.loads(POEMS.read_text(encoding='utf-8'))
    if isinstance(poems, dict):
        poems = poems.get('poems') or []
    keys = {}
    for p in poems:
        t = norm(p.get('title'))
        if t:
            keys.setdefault(t, []).append(p.get('id'))
        if p.get('subtitle'):
            full = norm(str(p.get('title')) + str(p.get('subtitle')))
            if full:
                keys.setdefault(full, []).append(p.get('id'))
    return poems, keys


def is_jh(vol):
    """初中与高中：这一轮的口径只看这两个学段。小学 12 册的目录里大量是识字课与现代文课文，
    不在「背诵篇目」这条线上，混进来只会把表变成噪音。"""
    return bool(re.search(r'七年级|八年级|九年级|必修|选择性', vol or ''))


def gap_rows(lessons, keys):
    out = []
    for vol, blk in (lessons.get('volumes') or {}).items():
        for e in (blk.get('entries') or []):
            title = (e.get('title') or '').strip()
            if not title:
                continue
            n = norm(title)
            if not n:
                continue
            if n in keys:
                continue
            if n in keys:
                continue
            if not is_jh(vol):
                continue
            out.append({'volume': vol, 'lesson': e.get('lesson') or ('自读' if e.get('selfReading') else ''),
                        'title': title, 'url': e.get('url') or '',
                        'looksModern': bool(MODERN.search(title)), 'recite': bool(e.get('selfReading'))})
    return out


def gap_rows_all(lessons, keys):
    """小学 12 册只数不列。"""
    n = 0
    for vol, blk in (lessons.get('volumes') or {}).items():
        if is_jh(vol):
            continue
        for e in (blk.get('entries') or []):
            t = (e.get('title') or '').strip()
            if not t:
                continue
            if norm(t) in keys:
                continue
            n += 1
    return n


def render(rows, counts):
    lines = ['# 统编教材收了、仓里对不上的课文（反向核对）', '',
             '这张表由 `tools/check-textbook-coverage-reverse.py` 生成，生成时间 %s。' % counts['generated'],
             '',
             '**怎么对的**：教材目录里的篇名（剥空白与标点）与仓内篇名、篇名+副标题比；',
             '只按「剥完标点一模一样」算对上——「长相思」不许顶掉「相思」（先前有过这种错），近似包含一律不算对上。',
             '**这张表不判该不该收。** 「看着像现当代课文」那一列只是把一眼不在仓的口径里的条目挑出来少报噪音，',
             '它不是裁定；剩下的每一条都要人逐条定口径。',
             '',
             '| 学段/册次 | 课号 | 教材篇名 | 看着像现当代课文 |',
             '| --- | --- | --- | --- |']
    for r in rows:
        lines.append('| %s | %s | %s | %s |' % (r['volume'], r['lesson'] or '诵读', r['title'], '像' if r['looksModern'] else '—'))
    lines += ['', '初中+高中 共 %d 条对不上（排在单元末诵读那一档的 %d 条、「看着像现当代课文」%d 条）。'
               % (counts['total'], counts['reciteGaps'], counts['modern']),
               '小学 12 册只数不列：%d 条。' % counts['primaryGaps'], '']
    return '\n'.join(lines)


def selftest():
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    keys = {'静女': ['jingnv'], '渔家傲秋思': ['yujiaao-qiusi']}
    lessons = {'volumes': {'必修上册': {'entries': [
        {'title': '静女', 'lesson': '诵读'},
        {'title': '渔家傲·秋思', 'lesson': '诵读'},
        {'title': '商山早行', 'lesson': '诵读'},
        {'title': '纪念白求恩', 'lesson': '13'},
        {'title': '', 'lesson': ''},
    ]}}}
    rows = gap_rows(lessons, keys)
    got = {r['title'] for r in rows}
    must('静女' not in got, '坏例1：仓里有的篇目被报成缺口')
    must('渔家傲·秋思' not in got, '坏例2：教材篇名带副标题、仓内是篇名+副标题，没对上')
    must('商山早行' in got, '坏例3：真缺口没被数出来')
    must('纪念白求恩' in got, '坏例4：一眼不在仓口径里的条目也要出现在表里（这张表不替人裁定）')
    must('' not in got, '坏例5：目录里的空篇名被当成一篇')
    must(next(r for r in rows if r['title'] == '纪念白求恩')['looksModern'], '坏例6：现当代课文没被标出来')
    must(not next(r for r in rows if r['title'] == '商山早行')['looksModern'], '坏例7：古诗文被标成现当代课文')
    # 坏例8：近似包含不许算对上得太宽——「长相思」不许顶掉「相思」
    rows2 = gap_rows({'volumes': {'九年级上册': {'entries': [{'title': '长相思', 'lesson': ''}]}}}, {'相思': ['xiangsi']})
    must(len(rows2) == 1, '坏例8：「长相思」被仓内「相思」近似吃掉，缺口没被数出来')
    # 坏例9：小学册不在这一轮口径里，不许混进表（只数不列由 gap_rows_all 负责）
    must(gap_rows({'volumes': {'一年级下册': {'entries': [{'title': '秋天', 'lesson': ''}]}}}, {}) == [],
         '坏例9：小学册的条目被列进了初中+高中这张表')
    must(gap_rows_all({'volumes': {'一年级下册': {'entries': [{'title': '秋天', 'lesson': ''}]}}, '必修上册': {'entries': [{'title': '静女', 'lesson': ''}]}}, {'静女': ['jingnv']}) == 1,
         '坏例10：小学缺口没被数出来，或仓内已有的篇目被数成缺口')
    return tried[0]


def main():
    import sys
    if '--selftest' in sys.argv:
        n = selftest()
        print('[ok] check-textbook-coverage-reverse --selftest 通（当场数到 %d 个坏例子，全部试到）' % n)
        return 0
    if not LESSONS.exists():
        print('[跳过] data/textbook-lessons.json 不在，反向核对没跑')
        return 0
    lessons = json.loads(LESSONS.read_text(encoding='utf-8'))
    poems, keys = load_poem_keys()
    rows = gap_rows(lessons, keys)
    modern = sum(1 for r in rows if r['looksModern'])
    recite = sum(1 for r in rows if r['recite'])
    counts = {'generated': lessons.get('generated') or '', 'total': len(rows), 'modern': modern,
              'lessonEntries': sum(len(b.get('entries') or []) for b in (lessons.get('volumes') or {}).values()),
              'poems': len(poems), 'reciteGaps': recite, 'primaryGaps': gap_rows_all(lessons, keys)}
    OUT_JSON.write_text(json.dumps({'note': '统编教材收了、仓里对不上的课文。这张表不判该不该收。',
                                    'generated': counts['generated'], 'counts': counts, 'rows': rows},
                                   ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(render(rows, counts), encoding='utf-8')
    print('[反向核对] 教材目录 %d 条 / 仓内 %d 篇：对不上的 %d 条（看着像现当代课文 %d 条）→ docs/textbook-gaps.md'
          % (counts['lessonEntries'], counts['poems'], counts['total'], counts['modern']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
