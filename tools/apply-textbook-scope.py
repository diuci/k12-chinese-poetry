#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「统编教材用字尚未逐本核对（P3 待办）」这类过期话换成核对表当场数出来的那句话。

为什么要有这个工具：仓里几十篇的「收录范围」还写着「尚未逐本核对」，可教材核对
（tools/check-textbook.py）早就把每一句比过了。文档里留一句其实做完了的事比不写更坏：
读者以为这一篇没查，而实际上查过。这种话必须由数据生成，不许手抄。"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STALE = ('P3 待办', '尚未逐本核对')
NL = chr(10)


def load_json(name):
    p = ROOT / 'data' / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))


def stale_lines(text):
    """篇内哪几行是「其实做完了却写着没做」的话。返回 [(行号, 缩进, 原句)]。"""
    out = []
    for n, line in enumerate(text.split(NL)):
        if any(k in line for k in STALE):
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
        return ('%s统编教材用字已逐句核过：本篇 %d 句可比，%d 句与统编%s一致；单字出入 %d 处逐处写在「异文」那一节'
                '（另有 %d 处是段落边界、教材夹注、节选范围造成的错位，不是文字分歧）。出处：统编课文页（镜像） %s'
                % (indent, total, hit, _lesson_of(row) or '教材', k, g, _url_of(row)))
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


def _title_of(text):
    m = re.search(r'^title:\s*(.+)$', text, re.M)
    return m.group(1).strip() if m else None


def plan(poems, atts):
    """返回 (改动列表, 没法定句的篇目)。"""
    changes, problems = [], []
    for p in poems:
        text = p.read_text(encoding='utf-8')
        found = stale_lines(text)
        if not found:
            continue
        row = atts.get(p.stem) or atts.get(_title_of(text))
        for n, indent, old in found:
            new = replacement(row, indent)
            if (new and '节选' in old and '节选' not in new
                    and row.get('status') in ('match', 'partial', 'title-variant', 'claimed-absent-but-present')):
                # 旧句里还提着一件真没定论的事（教材节选到哪儿为止），换句子不许把它悄悄抹掉
                new += ' 另：仓内收的是全篇，统编收的是节选，节选止点统编没标，我们不下结论。'
            if not new:
                problems.append('%s：篇内写着「%s」，核对表里却没有这篇的结论——不许凭空写核对结果' % (p.name, old[:28]))
                continue
            changes.append((p, n, old, new))
    return changes, problems


def selftest():
    """坏例子：这句话必须由核对表撑着，核对表没有结论时不许造。"""
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    match_row = {'status': 'match', 'hit': 7, 'total': 7, 'lesson': '21 古诗三首', 'volume': '五年级上册',
                 'url': 'https://x/1', 'charDiffs': [], 'ghostDiffs': 0}
    r1 = replacement(match_row)
    must('7 句可比' in r1 and '没有字面出入' in r1, '坏例1：核对结论没被写进句子：%s' % r1)
    must('https://x/1' in r1, '坏例2：换出来的句子没带出处')
    partial_row = {'status': 'partial', 'hit': 13, 'total': 20, 'lesson': '9 屈原列传', 'volume': '选择性必修中册',
                   'url': 'https://x/2', 'charDiffs': [{'ours': '眛', 'textbook': '眜'}] * 7, 'ghostDiffs': 5}
    r2 = replacement(partial_row)
    must('单字出入 7 处' in r2 and '另有 5 处' in r2, '坏例3：partial 的单字出入处数没写出来：%s' % r2)
    must(replacement(None) is None, '坏例4：没有核对记录却造出了一句话')
    must(replacement({'status': 'match'}) is None, '坏例5：核对表里没有句数也照样编了一句')
    must('未收' in replacement({'status': 'no-textbook'}), '坏例6：no-textbook 被写成了收了')
    must('只收了一部分' in replacement({'status': 'coverage-partial', 'lessons': [{'volume': '选择性必修上册', 'lesson': '6.1', 'title': '《老子》四章'}], 'url': 'https://x/3'}),
         '坏例7：coverage-partial 被写成了全收')
    must('语文园地' in replacement({'status': 'garden-attested', 'gardenVolume': '一年级上册', 'gardenTitle': '古朗月行（节选）', 'section': '语文园地六', 'url': 'https://x/4'}),
         '坏例8：园地那一档没说出收在园地')
    must('另一篇' in replacement({'status': 'mismatch', 'url': 'https://x/5'}), '坏例9：同名另一篇这一档没交代清楚')
    must(replacement(match_row, '  ').startswith('  统编'), '坏例10：缩进丢了，替换后会破坏列表结构')
    must(stale_lines('x' + NL + '  - 统编教材用字尚未逐本核对（P3 待办）。') == [(1, '  ', '- 统编教材用字尚未逐本核对（P3 待办）。')],
         '坏例11：过期话没被认出来或缩进没认出来')
    must(stale_lines('x' + NL + '本篇正文与教材一致。') == [], '坏例12：正常篇被当成有过期话')
    must('都没有它' in replacement({'status': 'lesson-not-found'}), '坏例13：lesson-not-found 这一档没写清查过哪里')
    print('[ok] apply-textbook-scope --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


def main():
    if '--selftest' in sys.argv:
        return selftest()
    write = '--write' in sys.argv
    att_raw = load_json('textbook-attestations.json')
    if not att_raw:
        print('缺 data/textbook-attestations.json：先跑 python tools/check-textbook.py')
        return 1
    atts = {}
    for row in att_raw.get('results', []):
        if row.get('id'):
            atts[row['id']] = row
        if row.get('title'):
            atts.setdefault(row['title'], row)
    poems = [p for p in sorted((ROOT / 'poems').rglob('*.md')) if p.name != '索引.md']
    changes, problems = plan(poems, atts)
    for p, n, old, new in changes:
        print('%s:%d' % (p.relative_to(ROOT), n + 1))
        print('  旧：' + old[:120])
        print('  新：' + new[:160])
    if problems:
        print('!! 没法定句的篇目（%d）：' % len(problems))
        for x in problems:
            print('  · ' + x)
    if write:
        by_file = {}
        for p, n, old, new in changes:
            by_file.setdefault(p, []).append((n, old, new))
        for p, items in by_file.items():
            lines = p.read_text(encoding='utf-8').split(NL)
            for n, old, new in items:
                if lines[n].strip() != old:
                    print('!! %s 第 %d 行内容变了，跳过' % (p.name, n + 1))
                    continue
                lines[n] = new
            p.write_text(NL.join(lines), encoding='utf-8')
        print('已改写 %d 处（%d 个文件）' % (len(changes), len(by_file)))
    else:
        print('（空跑：加 --write 才改文件）')
    if problems:
        return 1
    if not write and changes:
        # 空跑却还有可换的：说明篇内留着过期的话，链条不许绿
        print('还有 %d 处过期话没换：跑 python tools/apply-textbook-scope.py --write' % len(changes))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())