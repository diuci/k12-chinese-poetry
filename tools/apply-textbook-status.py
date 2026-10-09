#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给每篇 frontmatter 写上 textbookStatus：这一篇统编教材到底收没收。

为什么要有这个字段：仓里 52 篇是「课标要求背、统编教材课本里没有这一课」，
3 篇是「教材里那篇同名的是另一首诗」。这两件事以前只写在 data/volume-findings.json 里，
篇目文件自己不说，站点也就没法告诉学生「这篇教材不教，但课标要背」。

取值只有四种（`ALLOWED` 就是这个清单，多一档少一档 --selftest 都会当场报错）：
  统编教材收录
  统编教材未收（课标要求）
  统编教材收的是同名另一篇
  统编教材收在别的课里

结论全部从 data/volume-findings.json 来，不许手写。默认空跑，--write 才写盘。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTED = '统编教材收录'
NOT_COLLECTED = '统编教材未收（课标要求）'
NAME_CLASH = '统编教材收的是同名另一篇'
# 第四种：教材收了，但收在别的课里、篇名不一样（课标叫《孟子》三则，教材叫鱼我所欲也/富贵不能淫/生于忧患死于安乐）。
# 按标题去教材目录里找不到，以前被判成「教材未收」——那是错的：它告诉学生教材没有这一课，而教材明明有。
COVERED_ELSEWHERE = '统编教材收在别的课里'
# 第五档：教材收了，但只收了课标要求的一部分（课标要《老子》八章，教材那一课只有四章）。
# 这一档不许并进「收在别的课里」：那等于告诉学生教材全覆盖了，缺的部分就不背了。
PARTIAL = '统编教材收了一部分（课标要求更多）'
ALLOWED = (COLLECTED, NOT_COLLECTED, NAME_CLASH, COVERED_ELSEWHERE, PARTIAL)
COVERAGE_PATH = ROOT / 'data' / 'textbook-coverage.json'


def status_of(finding, volume):
    if volume == '选修（2026起默写）':
        return NOT_COLLECTED
    if finding is None:
        return None
    st = finding['status']
    if st in ('match', 'title-variant', 'claimed-absent-but-present'):
        return COLLECTED
    if st == 'title-collision':
        return NAME_CLASH
    if st == 'absent':
        return NOT_COLLECTED
    if st == 'volume-mismatch':
        return None
    return None


def status_with_coverage(finding, volume, cov_entry):
    """先按教材目录的核对结论定档，再看覆盖表。

    覆盖表只在「按标题找不到这一课」时才有内容：它说的是教材把这篇收在别的课里，
    所以它必须盖过「教材未收」——否则就告诉学生教材没有这一课，而教材明明有。
    但它不许盖过「教材收的是同名另一篇」：那一篇教材里真有一个同名的是别的内容，
    这一条是给学生认篇名用的，覆盖表说「收在别的课里」并不能把它变成同一篇。
    """
    st = status_of(finding, volume)
    if cov_entry and st != NAME_CLASH:
        # partial 只许把「收了」降级成「收了一部分」，不许把「收了一部分」升级成「收了」
        return PARTIAL if cov_entry.get('partial') else COVERED_ELSEWHERE
        return COVERED_ELSEWHERE
    return st


def cover_label(lesson):
    """写进 frontmatter 的「教材收在哪一课」。篇名自己带书名号的不许再套一层——
    「《《老子》四章》」这种写法在页面上就是错相。"""
    t = lesson['title']
    return '%s%s' % (lesson['volume'], t if t.startswith('《') else '《%s》' % t)


def selftest():
    """这个脚本会往每篇 md 的 frontmatter 里写「统编教材收没收」，写错了就是对学生说假话。
    所以它必须自带坏例子。"""
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    # 坏例1：选修册（2026 起默写）教材里没有这一课，哪怕目录里撞见同名也必须判「未收」
    must(status_of({'id': 'x', 'status': 'match'}, '选修（2026起默写）') == NOT_COLLECTED,
         '坏例1：选修册被判成教材收录')
    # 坏例2：没有核对结论就是「判不出」，不许默认成收录，也不许默认成未收
    must(status_of(None, '七年级上册') is None, '坏例2：没有核对结论却有默认结论')
    # 坏例3：册次对不上（volume-mismatch）不是「收没收」的问题，不许顺手判成未收
    must(status_of({'id': 'x', 'status': 'volume-mismatch'}, '七年级上册') is None,
         '坏例3：册次问题被当成教材未收')
    # 坏例4：同名撞车必须单独一档——它告诉学生「教材里那篇同名的是另一首诗」
    must(status_of({'id': 'x', 'status': 'title-collision'}, '八年级上册') == NAME_CLASH,
         '坏例4：同名撞车没被单独登记')
    # 坏例5：仓里写着没收、教材目录里却有——必须判收录，这是以前判错的那一类
    must(status_of({'id': 'x', 'status': 'claimed-absent-but-present'}, '八年级上册') == COLLECTED,
         '坏例5：教材明明收了却被判未收')
    # 坏例6：没见过的 status 一律「判不出」，不许默认成收录——默认成收录就是说假话
    must(status_of({'id': 'x', 'status': 'looks-fine-to-me'}, '八年级上册') is None,
         '坏例6：没见过的 status 被默认成有结论')
    # 坏例7：ALLOWED 四档必须每一档都造得出来，有一档是死的就说明字段与规则脱节了
    produced = {status_of({'id': 'a', 'status': s}, '七年级上册') for s in
                ('match', 'title-variant', 'claimed-absent-but-present', 'title-collision', 'absent')}
    produced.add(status_of({'id': 'b', 'status': 'match'}, '选修（2026起默写）'))
    produced.add(status_with_coverage({'id': 'c', 'status': 'absent'}, '七年级上册', {'lessons': []}))
    # 第五档（收了一部分）也得有规则能产出，否则 ALLOWED 里多了一档死的
    produced.add(status_with_coverage({'id': 'e', 'status': 'absent'}, '选择性必修上册',
                                     {'lessons': [{'volume': '选择性必修上册', 'title': '《老子》四章'}], 'partial': True}))
    for want in ALLOWED:
        must(want in produced, '坏例7：ALLOWED 里的「%s」没有任何规则能产出，字段与规则脱节' % want)
    # 坏例8：覆盖表必须盖过「教材未收」——教材把这篇收在别的课里，说「未收」就是假话
    must(status_with_coverage({'id': 'x', 'status': 'absent'}, '七年级上册', {'lessons': [{'volume': '七年级上册', 'title': '鱼我所欲也'}]}) == COVERED_ELSEWHERE,
         '坏例8：覆盖表没盖过「教材未收」')
    # 坏例9：覆盖表不许盖过「同名另一篇」——那一条是给学生认篇名用的
    must(status_with_coverage({'id': 'x', 'status': 'title-collision'}, '八年级上册', {'lessons': []}) == NAME_CLASH,
         '坏例9：覆盖表把「同名另一篇」抹成了「收在别的课里」')
    # 坏例10：判不出就是判不出，覆盖表救不了它（覆盖表只说教材有这一课，不说这篇是谁）
    must(status_with_coverage(None, '七年级上册', None) is None, '坏例10：没有核对结论却被覆盖表填上了结论')

    # 坏例11：partial 必须单独一档——教材只收四章、课标要八章，写成「收在别的课里」就是全覆盖
    must(status_with_coverage({'id': 'x', 'status': 'absent'}, '选择性必修上册',
                             {'lessons': [{'volume': '选择性必修上册', 'title': '《老子》四章'}], 'partial': True}) == PARTIAL,
         '坏例11：只收了一部分被写成了「收在别的课里」（全覆盖）')
    # 坏例12：partial 也不许退回「教材未收」——教材确实收了四章
    must(status_with_coverage({'id': 'x', 'status': 'absent'}, '选择性必修上册',
                             {'lessons': [{'volume': '选择性必修上册', 'title': '《老子》四章'}], 'partial': True}) != NOT_COLLECTED,
         '坏例12：教材收了四章被判成教材未收')
    # 坏例13：partial 不许盖过「同名另一篇」
    must(status_with_coverage({'id': 'x', 'status': 'title-collision'}, '八年级上册',
                             {'lessons': [], 'partial': True}) == NAME_CLASH,
         '坏例13：partial 把「同名另一篇」抹掉了')
    # 坏例14：ALLOWED 现在五档，每一档都得有规则能产出（有一档是死的就是字段与规则脱节）
    produced2 = set(produced)
    produced2.add(status_with_coverage({'id': 'd', 'status': 'absent'}, '七年级上册',
                                       {'lessons': [{'volume': '七年级上册', 'title': 'x'}], 'partial': True}))
    for want in ALLOWED:
        must(want in produced2, '坏例14：ALLOWED 里的「%s」没有任何规则能产出' % want)

    # 坏例15：篇名自己带书名号，不许再套一层
    must(cover_label({'volume': '选择性必修上册', 'title': '《老子》四章'}) == '选择性必修上册《老子》四章',
         '坏例15：书名号被套成两层（%s）' % cover_label({'volume': '选择性必修上册', 'title': '《老子》四章'}))
    must(cover_label({'volume': '七年级下册', 'title': '木兰诗'}) == '七年级下册《木兰诗》',
         '坏例15b：不带书名号的篇名没被包上')

    print('[ok] apply-textbook-status --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


def main():
    write = '--write' in sys.argv
    poems = json.loads((ROOT / 'data' / 'poems.json').read_text(encoding='utf-8'))['poems']
    f = json.loads((ROOT / 'data' / 'volume-findings.json').read_text(encoding='utf-8'))
    # absent / title-collision 两类不在 findings 里，各自单列，这里要一并收进来。
    # 只读 findings 的话这 55 篇全被判成「判不出状态」，看着像工具坏了，其实是漏读了两张表。
    by_id = {x['id']: x for x in f['findings']}
    for x in f.get('absent', []):
        by_id[x['id']] = {'id': x['id'], 'status': 'absent'}
    for x in f.get('titleCollision', []):
        by_id[x['id']] = {'id': x['id'], 'status': 'title-collision'}
    # 覆盖表是人定的，但每一条都要能在 data/textbook-lessons.json 里找到那一课；找不到就是编的，直接报错。
    cov = json.loads(COVERAGE_PATH.read_text(encoding='utf-8')).get('coverage', {}) if COVERAGE_PATH.exists() else {}
    lesson_index = set()
    tl = json.loads((ROOT / 'data' / 'textbook-lessons.json').read_text(encoding='utf-8'))
    for vol, v in tl['volumes'].items():
        for l in v['entries']:
            lesson_index.add((vol, l['title']))
    cov_problems = []
    for pid, cv in cov.items():
        if len(cv.get('sources') or []) < 2:
            cov_problems.append('%s 覆盖表里没写满两条独立来源' % pid)
        for l in cv['lessons']:
            if (l['volume'], l['title']) not in lesson_index and \
               (l['volume'], l.get('indexTitle') or '') not in lesson_index:
                cov_problems.append('textbook-coverage.json 里 %s 说教材有「%s」（%s），但教材目录表里找不到这一课' % (pid, l['title'], l['volume']))
    if cov_problems:
        # 以前这里调了一个不存在的 die()：覆盖表一有问题就 NameError 崩掉，
        # 看着像工具坏了，其实是把「哪一条是编的」这句话吞掉了。
        for x in cov_problems:
            print('  !! ' + x)
        return 1
    plan, unknown = [], []
    for p in poems:
        cv = cov.get(p['id'])
        st = status_with_coverage(by_id.get(p['id']), p.get('volume') or '', cv)
        if st is None:
            unknown.append((p['title'], p.get('volume')))
            continue
        path = ROOT / p['_path']
        text = path.read_text(encoding='utf-8')
        m = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
        if not m:
            unknown.append((p['title'], 'frontmatter 读不出来'))
            continue
        fm = m.group(1)
        if re.search(r'^textbookStatus:', fm, re.M):
            fm2 = re.sub(r'^textbookStatus:.*$', 'textbookStatus: %s' % st, fm, count=1, flags=re.M)
        else:
            fm2 = fm + '\ntextbookStatus: %s' % st
        if cv:
            by = '；'.join(cover_label(l) for l in cv['lessons'])
            if re.search(r'^textbookCoveredBy:', fm2, re.M):
                fm2 = re.sub(r'^textbookCoveredBy:.*$', 'textbookCoveredBy: %s' % by, fm2, count=1, flags=re.M)
            else:
                fm2 = fm2 + '\ntextbookCoveredBy: %s' % by
        elif re.search(r'^textbookCoveredBy:', fm2, re.M):
            fm2 = re.sub(r'^textbookCoveredBy:.*$\n?', '', fm2, count=1, flags=re.M)
        if fm2 == fm:
            continue
        plan.append((p['stage'], p['title'], st, path))
        if write:
            path.write_text('---\n' + fm2 + '\n---\n' + text[m.end():], encoding='utf-8')
    tally = {}
    for _s, _t, st, _p in plan:
        tally[st] = tally.get(st, 0) + 1
    print('要写 textbookStatus：%d 篇%s' % (len(plan), '' if write else '（空跑，未写盘）'))
    for k in ALLOWED:
        print('  %-24s %d' % (k, tally.get(k, 0)))
    if unknown:
        print()
        print('判不出状态 %d 篇（这些必须先查清楚，不许默认成任何一种）' % len(unknown))
        for t, v in unknown:
            print('  %-22s volume=%s' % (t, v))
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
