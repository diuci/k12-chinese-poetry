#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「统编教材用字尚未逐本核对（P3 待办）」这类过期话、以及句数过期的核对结论，换成核对表当场数出来的那句话。

为什么要有这个工具：仓里几十篇的「收录范围」写着「尚未逐本核对」，可教材核对（tools/check-textbook.py）
早就把每一句比过了；核对表一更新，篇内那句「本篇 N 句可比」也跟着过期。假待办与旧数字都比没写更坏。
这种话必须由数据生成，不许手抄。"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STALE = ('P3 待办', '尚未逐本核对')
SCOPE_MARK = '统编教材用字已逐句核过'
SCOPE_NUM = re.compile(r'本篇 (\d+) 句可比，(\d+) 句')
NL = chr(10)


def load_json(name):
    p = ROOT / 'data' / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))


def _id_of(text):
    m = re.search(r'^id:\s*(.+)$', text, re.M)
    return m.group(1).strip() if m else None


def _title_of(text):
    m = re.search(r'^title:\s*(.+)$', text, re.M)
    return m.group(1).strip() if m else None


def stale_lines(text, row=None):
    """篇内哪几行需要重写：一是「其实做完了却写着没做」的过期话；
    二是核对表更新后句数对不上的那句话——数字过期跟话过期一样坏。"""
    out = []
    for n, line in enumerate(text.split(NL)):
        if any(k in line for k in STALE):
            out.append((n, line[:len(line) - len(line.lstrip())], line.strip()))
            continue
        if SCOPE_MARK in line and row is not None:
            m = SCOPE_NUM.search(line)
            if not m:
                out.append((n, line[:len(line) - len(line.lstrip())], line.strip()))
                continue
            if (int(m.group(1)), int(m.group(2))) != (row.get('total'), row.get('hit')):
                out.append((n, line[:len(line) - len(line.lstrip())], line.strip()))
    return out


def _lesson_of(row):
    ls = row.get('lessons') or []
    if ls:
        x = ls[0]
        return '%s第 %s 课《%s》' % (x.get('volume') or '', x.get('lesson') or '?', x.get('title') or '')
    if row.get('lesson'):
        return '%s「%s」' % (row.get('volume') or '', row['lesson'])
    return None


def _url_of(row):
    return row.get('url') or (row.get('lessons') or [{}])[0].get('url') or ''


def replacement(row, indent=chr(0)):
    """核对表当场数出来的那句话。没有核对记录就不许造句子——这是这条工具最重要的一条。"""
    indent = '' if indent == chr(0) else indent
    if not row:
        return None
    status = row.get('status')
    if status in ('match', 'title-variant', 'claimed-absent-but-present'):
        hit, total = row.get('hit'), row.get('total')
        if hit is None or total is None:
            return None
        cd = row.get('charDiffs') or []
        tail = '没有字面出入' if not cd else '单字出入 %d 处写在「异文」那一节' % len(cd)
        return ('%s统编教材用字已逐句核过：本篇 %d 句可比，%d 句与统编%s一致，%s。出处：统编课文页（镜像） %s'
                % (indent, total, hit, _lesson_of(row) or '教材', tail, _url_of(row)))
    if status == 'partial':
        hit, total = row.get('hit'), row.get('total')
        if hit is None or total is None:
            return None
        k = len(row.get('charDiffs') or [])
        g = row.get('ghostDiffs') or 0
        seg = ('单字出入 %d 处逐处写在「异文」那一节' % k) if k else '没有字面出入'
        extra = ('（另有 %d 处是段落边界、教材夹注、节选范围造成的错位，不是文字分歧）' % g) if g else ''
        return ('%s统编教材用字已逐句核过：本篇 %d 句可比，%d 句与统编%s一致；%s%s。出处：统编课文页（镜像） %s'
                % (indent, total, hit, _lesson_of(row) or '教材', seg, extra, _url_of(row)))
    if status == 'coverage-override':
        return ('%s统编教材收了本篇，但篇名与课标不同：收在统编%s。仓内沿用课标篇名，教材篇名登记在 data/textbook-coverage.json。'
                '出处：统编课文页（镜像） %s' % (indent, _lesson_of(row) or '教材', _url_of(row)))
    if status == 'coverage-partial':
        return ('%s统编教材只收了一部分：统编%s。没收的那几章仍按课标要背，不许拿教材目录当「不用背」。'
                '出处：统编课文页（镜像） %s' % (indent, _lesson_of(row) or '教材', _url_of(row)))
    if status == 'garden-attested':
        return ('%s统编教材收本篇的地方不是课文，是%s《%s》「%s」。出处：统编园地页（镜像） %s'
                % (indent, row.get('gardenVolume') or '', row.get('gardenTitle') or row.get('title') or '',
                   row.get('section') or '', _url_of(row)))
    if status == 'no-textbook':
        return ('%s统编教材课本未收这一篇（课标指定的选修／拓展篇目）：仓内这一篇的正文不来自教材，'
                '核对表记为 no-textbook。' % indent)
    if status == 'lesson-not-found':
        return ('%s课标要求这一篇，统编教材的课文目录与单元末诵读里都没有它（核对表记为 lesson-not-found；'
                '查过哪些目录写在 data/textbook-attestations.json 的 note 里）。' % indent)
    if status == 'mismatch':
        return ('%s统编教材里同名的是另一篇（核对表记为 mismatch）：仓内这一篇的正文与教材那一页一句都没对上。'
                '出处：统编课文页（镜像） %s' % (indent, _url_of(row)))
    return None


def plan(poems, atts):
    """返回 (改动列表, 没法定句的篇目)。"""
    changes, problems = [], []
    for p in poems:
        text = p.read_text(encoding='utf-8')
        # 按 frontmatter 的 id 找：同名两篇（渔家傲有「秋思」与「天接云涛」两首）按篇名找会挑错那一条
        row = atts.get(_id_of(text)) or atts.get(p.stem) or atts.get(_title_of(text))
        found = stale_lines(text, row)
        if not found:
            continue
        for n, indent, old in found:
            new = replacement(row, indent)
            if (new and '节选' in old and '节选' not in new
                    and row.get('status') in ('match', 'partial', 'title-variant', 'claimed-absent-but-present')):
                # 旧句里还提着一件真没定论的事（教材节选到哪儿为止），换句子不许把它悄悄抹掉
                new += ' 另：仓内收的是全篇，统编收的是节选，节选止点统编没标，我们不下结论。'
            if not new:
                problems.append(p.name)
                continue
            if new.strip() == old:
                continue
            changes.append((p, n, old, new))
    return changes, problems


def selftest():
    """坏例子：每一类结论都要试到，尤其「没有核对记录就不许造句子」。"""
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    match_row = {'status': 'match', 'hit': 15, 'total': 15, 'lesson': '16.1 短文两篇', 'volume': '七年级上册',
                   'url': 'https://x/1', 'charDiffs': []}
    r = replacement(match_row, '  ')
    must(r and '本篇 15 句可比，15 句' in r and r.startswith('  '), '坏例1：match 的句数没写出来或缩进丢了：%s' % r)
    must(replacement(None) is None, '坏例2：没有核对记录也造出了句子')
    must(replacement({'status': 'match', 'lesson': 'x', 'url': 'u'}) is None, '坏例3：句数缺失也照写')
    partial_row = {'status': 'partial', 'hit': 13, 'total': 20, 'lesson': '15.1 阿房宫赋', 'volume': '必修下册',
                    'url': 'https://x/2', 'charDiffs': [{'ours': 'x', 'textbook': 'y'}] * 7, 'ghostDiffs': 5}
    r2 = replacement(partial_row, '')
    must('单字出入 7 处' in r2 and '另有 5 处' in r2, '坏例3b：partial 的单字出入处数没写出来：%s' % r2)
    r2b = replacement(dict(partial_row, charDiffs=[], ghostDiffs=0))
    must('没有字面出入' in r2b and '另有' not in r2b, '坏例3c：没有出入的 partial 被写成有出入：%s' % r2b)
    r2c = replacement(dict(partial_row, charDiffs=[], ghostDiffs=5))
    must('没有字面出入' in r2c and '另有 5 处' in r2c, '坏例3d：只有残影的 partial 没说明残影不是分歧：%s' % r2c)
    must('同名另一篇' not in r2, '坏例4：partial 被写成「同名另一篇」')
    ov = {'status': 'coverage-override', 'lessons': [{'volume': '八年级上册', 'lesson': '6.2', 'title': '丑奴儿·说尽心中无限事', 'url': 'https://x/3'}],
          'url': 'https://x/3'}
    r3 = replacement(ov, '')
    must('八年级上册' in r3 and '丑奴儿' in r3, '坏例5：coverage-override 没写出统编那课在哪：%s' % r3)
    gp = {'status': 'coverage-partial', 'lessons': [{'volume': '选择性必修上册', 'lesson': '6.1', 'title': '老子四章', 'url': 'https://x/4'}], 'url': 'https://x/4'}
    must('只收了一部分' in replacement(gp, ''), '坏例6：coverage-partial 被写成全收')
    ga = {'status': 'garden-attested', 'gardenVolume': '八年级上册', 'gardenTitle': '渔家傲', 'section': '课外诵读',
          'url': 'https://x/5', 'hit': 9, 'total': 9}
    r4 = replacement(ga, '')
    must('课外诵读' in r4 and '不是课文' in r4, '坏例7：园地档被写成课文：%s' % r4)
    must('未收' in replacement({'status': 'no-textbook'}, ''), '坏例8：no-textbook 没写未收')
    must('都没有它' in replacement({'status': 'lesson-not-found'}, ''), '坏例9：lesson-not-found 没写教材里没有')
    must(replacement({'status': '从没见过的结论'}, '') is None, '坏例10：没见过的结论被硬编成一句话')
    must(stale_lines('  - 统编教材用字尚未逐本核对（P3 待办）。') == [(0, '  ', '- 统编教材用字尚未逐本核对（P3 待办）。')],
         '坏例11：过期话没被认出来或缩进没认出来')
    must(stale_lines('x' + NL + '本篇正文与教材一致。') == [], '坏例12：正常篇被当成有过期话')
    row24 = {'status': 'match', 'hit': 9, 'total': 9, 'lesson': '11.1 过秦论', 'volume': '选择性必修中册',
             'url': 'https://x/6', 'charDiffs': [], 'ghostDiffs': 0}
    must(len(stale_lines('  ' + SCOPE_MARK + '：本篇 11 句可比，10 句与统编一致。', row24)) == 1,
         '坏例13：核对表变成 9/9，篇内还写着 10/11，没被认出来要重写')
    must(stale_lines('  ' + SCOPE_MARK + '：本篇 9 句可比，9 句与统编一致，没有字面出入。', row24) == [],
         '坏例14：数字跟核对表一致的那句话被误判成过期')
    must(len(stale_lines('  ' + SCOPE_MARK + '：核对过了。', row24)) == 1, '坏例15：没有句数的核对话没被抓出来重写')
    must(_id_of('---' + NL + 'id: yujiaao-tianjie' + NL + 'title: 渔家傲' + NL) == 'yujiaao-tianjie',
         '坏例16：篇内 id 没被读出来，同名两篇会挑错核对结论')
    must('节选' not in replacement({'status': 'no-textbook'}, ''),
         '坏例17：教材没收的篇被加上一句「统编收的是节选」')
    return tried[0]


def main():
    write = '--write' in sys.argv
    if selftest() < 15:
        print('自检没试够')
        return 1
    if '--selftest' in sys.argv:
        print('[ok] apply-textbook-scope --selftest 通（当场数到 %d 个坏例子，全部试到）' % selftest())
        return 0
    att_raw = load_json('textbook-attestations.json')
    if not att_raw:
        print('缺 data/textbook-attestations.json：先跑 python tools/check-textbook.py')
        return 1
    atts = {}
    for a in att_raw.get('results') or []:
        atts.setdefault(a.get('id'), a)
        atts.setdefault(a.get('title'), a)
    poems = sorted((ROOT / 'poems').rglob('*.md'))
    changes, problems = plan(poems, atts)
    for p, n, old, new in changes:
        print('%s:%d' % (p.relative_to(ROOT), n + 1))
        print('  旧：' + old[:120])
        print('  新：' + new[:120])
    if problems:
        print('没法定句（核对表里没有这篇或结论没认出来）：%s' % '、'.join(problems[:12]))
    if not write:
        print('（空跑：加 --write 才改文件）' if changes else '（没有过期话要换）')
        return 1 if changes else 0
    for p, n, old, new in changes:
        lines = p.read_text(encoding='utf-8').split(NL)
        lines[n] = new
        p.write_text(NL.join(lines), encoding='utf-8')
    print('已改写 %d 处（%d 个文件）' % (len(changes), len({c[0] for c in changes})))
    return 0


if __name__ == '__main__':
    sys.exit(main())
