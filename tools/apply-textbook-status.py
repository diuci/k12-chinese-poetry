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
  统编教材收了一部分（课标要求更多）
  统编教材收了（只有一条来源）
  统编教材里没找到这一课

结论全部从 data/volume-findings.json 来，不许手写。默认空跑，--write 才写盘。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import validate as V  # noqa: E402  「课标篇目 / 教材拓展」的口径只有一份，在 validate.py 里
COLLECTED = '统编教材收录'
NOT_COLLECTED = '统编教材未收（课标要求）'
NAME_CLASH = '统编教材收的是同名另一篇'
# 第四种：教材收了，但收在别的课里、篇名不一样（课标叫《孟子》三则，教材叫鱼我所欲也/富贵不能淫/生于忧患死于安乐）。
# 按标题去教材目录里找不到，以前被判成「教材未收」——那是错的：它告诉学生教材没有这一课，而教材明明有。
COVERED_ELSEWHERE = '统编教材收在别的课里'
# 第五档：教材收了，但只收了课标要求的一部分（课标要《老子》八章，教材那一课只有四章）。
# 这一档不许并进「收在别的课里」：那等于告诉学生教材全覆盖了，缺的部分就不背了。
PARTIAL = '统编教材收了一部分（课标要求更多）'
# 第六档：语文园地页里有这一篇，可只核到一条来源（那个第三方镜像）。不许升格成「收录」（一条不够），
# 也不许反过来说「未收」（那条来源说的是收了）。这一档说的是证据的份数，不是教材有没有。
ONE_SOURCE = '统编教材收了（只有一条来源）'
# 第七档：仓里挂着统编教材的册次，可 23 册课文目录与 12 册语文园地页里都没找到这一课，而且它不是
# 课标篇目（教材拓展）。说的是「我们没找到」，不是「教材没有」——园地表里有几页只列了栏目头、没列篇名。
NOT_FOUND = '统编教材里没找到这一课'
ALLOWED = (COLLECTED, NOT_COLLECTED, NAME_CLASH, COVERED_ELSEWHERE, PARTIAL, ONE_SOURCE, NOT_FOUND)
COVERAGE_PATH = ROOT / 'data' / 'textbook-coverage.json'
GARDEN_RULES = ROOT / 'data' / 'garden-rulings.json'



def status_of(finding, volume, garden_hit=False, is_syllabus=True):
    if volume == '选修（2026起默写）':
        return NOT_COLLECTED
    if finding is None:
        return None
    st = finding['status']
    if st in ('match', 'title-variant', 'claimed-absent-but-present'):
        return COLLECTED
    if st == 'title-collision':
        return NAME_CLASH
    if st == 'garden-attested':
        # 语文园地收了、两条来源核过：教材确实收了，只是不在课文目录里
        return COLLECTED
    if st == 'absent':
        # 课文目录里没有，可同一册的语文园地页里有这一篇：手上有一条来源说收了，不能写成「未收」；
        # 但那条来源只是那个镜像，不够升格成「收录」。
        if garden_hit:
            return ONE_SOURCE
        # 不是课标篇目（教材拓展）的不许冒领「课标要求」——课标附录1里没有它
        return NOT_COLLECTED if is_syllabus else NOT_FOUND
    if st == 'volume-mismatch':
        return None
    return None


def garden_rule_ok(rule, volume):
    """语文园地裁定表的一条能不能决定「教材收了」：册次必须与仓内一致、来源两条以上、镜像最多一条。

    返回 (ok, why)。这张表说「收了」就是把一篇从「镜像里看到了」升格，门槛必须在这里复核。"""
    srcs = [x for x in (rule.get('sources') or []) if x]
    mirror = [x for x in srcs if 'yw.suyang123.com' in x]
    if rule.get('volume') != volume:
        return False, '裁定表说在「%s」，仓内挂在「%s」' % (rule.get('volume'), volume)
    if len(srcs) < 2:
        return False, '裁定表只有 %d 条来源，不够两条' % len(srcs)
    if len(mirror) > 1:
        return False, '裁定表 %d 条来源里 %d 条出自同一个镜像目录——同源不算两条' % (len(srcs), len(mirror))
    return True, ''


def status_with_coverage(finding, volume, cov_entry, garden_hit=False, is_syllabus=True):
    """先按教材目录的核对结论定档，再看覆盖表。

    覆盖表只在「按标题找不到这一课」时才有内容：它说的是教材把这篇收在别的课里，
    所以它必须盖过「教材未收」——否则就告诉学生教材没有这一课，而教材明明有。
    但它不许盖过「教材收的是同名另一篇」：那一篇教材里真有一个同名的是别的内容，
    这一条是给学生认篇名用的，覆盖表说「收在别的课里」并不能把它变成同一篇。
    """
    st = status_of(finding, volume, garden_hit, is_syllabus)
    if cov_entry and st != NAME_CLASH:
        # partial 只许把「收了」降级成「收了一部分」，不许把「收了一部分」升级成「收了」
        return PARTIAL if cov_entry.get('partial') else COVERED_ELSEWHERE
    return st


def status_with_garden(st, gr_ok):
    """园地裁定核过两条来源时，「教材未收」必须改成「教材收录」：教材确实收了，只是不在课文目录里。

    它只改「未收」这一档。不许把「同名另一篇」「收在别的课里」「收了一部分」改成「收录」——
    那三档说的是别的事，盖过去就是把缺的部分说成没缺。"""
    if gr_ok and st in (NOT_COLLECTED, ONE_SOURCE):
        return COLLECTED
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
    # 坏例7：ALLOWED 每一档都必须造得出来，有一档是死的就说明字段与规则脱节了
    produced = {status_of({'id': 'a', 'status': s}, '七年级上册') for s in
                ('match', 'title-variant', 'claimed-absent-but-present', 'title-collision', 'absent')}
    produced.add(status_of({'id': 'b', 'status': 'match'}, '选修（2026起默写）'))
    produced.add(status_with_coverage({'id': 'c', 'status': 'absent'}, '七年级上册', {'lessons': []}))
    # 第五档（收了一部分）也得有规则能产出，否则 ALLOWED 里多了一档死的
    produced.add(status_with_coverage({'id': 'e', 'status': 'absent'}, '选择性必修上册',
                                     {'lessons': [{'volume': '选择性必修上册', 'title': '《老子》四章'}], 'partial': True}))
    # 第六、七档也得有规则能产出——ALLOWED 里有一档是死的，就是字段与规则脱节
    produced.add(status_of({'id': 'f', 'status': 'absent'}, '一年级下册', True))
    produced.add(status_of({'id': 'g', 'status': 'absent'}, '一年级下册', False, False))
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
    # 坏例14：ALLOWED 现在七档，每一档都得有规则能产出（有一档是死的就是字段与规则脱节）
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

    # 坏例16~18：园地裁定的效力——只把「未收」升成「收录」，别的不许动
    must(status_with_garden(NOT_COLLECTED, True) == COLLECTED, '坏例16：园地两条来源核过了，还写着「教材未收」')
    must(status_with_garden(NOT_COLLECTED, False) == NOT_COLLECTED, '坏例16b：没有裁定也被升成收录')
    must(status_with_garden(NAME_CLASH, True) == NAME_CLASH, '坏例17：园地裁定把「同名另一篇」抹成了收录')
    must(status_with_garden(COVERED_ELSEWHERE, True) == COVERED_ELSEWHERE, '坏例17b：园地裁定把「收在别的课里」抹成了收录')
    must(status_with_garden(PARTIAL, True) == PARTIAL, '坏例18：园地裁定把「收了一部分」升成了收录')
    # 坏例19：园地裁定表自己的门槛
    ok, why = garden_rule_ok({'volume': '五年级下册', 'sources': ['镜像 yw.suyang123.com 园地页', 'zy.21cnjy.com/22255207 教案']}, '五年级下册')
    must(ok, '坏例19：册次对、两条来源（镜像一条）的裁定被误报：%s' % why)
    must(not garden_rule_ok({'volume': '五年级下册', 'sources': ['zy.21cnjy.com/22255207 教案']}, '五年级下册')[0],
         '坏例19b：只有一条来源的裁定被放行')
    must(not garden_rule_ok({'volume': '五年级下册', 'sources': ['yw.suyang123.com a', 'yw.suyang123.com b']}, '五年级下册')[0],
         '坏例19c：两条来源都出自同一个镜像却被放行')
    must(not garden_rule_ok({'volume': '六年级下册', 'sources': ['a', 'b']}, '五年级下册')[0],
         '坏例19d：裁定表说的册次与仓内不一致却被放行')

    # 坏例20：同一册的园地页里有这一篇，还写「统编教材未收（课标要求）」——手上那条来源说的是收了
    must(status_of({'id': 'x', 'status': 'absent'}, '三年级下册', True) == ONE_SOURCE,
         '坏例20：园地有一条来源却还判成「未收」')
    # 坏例21：只有一条来源不许升格成「统编教材收录」
    must(status_of({'id': 'x', 'status': 'absent'}, '三年级下册', True) != COLLECTED,
         '坏例21：一条来源被升格成「统编教材收录」')
    # 坏例22：教材拓展的篇目（课标附录1里没有它）不许冒领「课标要求」
    must(status_of({'id': 'x', 'status': 'absent'}, '一年级下册', False, False) == NOT_FOUND,
         '坏例22：不是课标篇目却写着「课标要求」')
    # 坏例22b：课标篇目不许写成「统编教材里没找到这一课」——那等于把课标要求抹掉
    must(status_of({'id': 'x', 'status': 'absent'}, '七年级上册', False, True) == NOT_COLLECTED,
         '坏例22b：课标篇目被写成「统编教材里没找到这一课」')
    # 坏例23：园地裁定核过两条来源，「只有一条来源」这一档必须被升格成收录（那三篇就靠这一条落地）
    must(status_with_garden(ONE_SOURCE, True) == COLLECTED,
         '坏例23：两条来源核过了还挂着「只有一条来源」')
    # 坏例23b：裁定表不成立时不许升格
    must(status_with_garden(ONE_SOURCE, False) == ONE_SOURCE,
         '坏例23b：没有裁定也被升成收录')
    # 坏例24：覆盖表不许把「只有一条来源」抹成「收在别的课里」——那是另一件事
    must(status_with_coverage({'id': 'x', 'status': 'absent'}, '三年级下册', {'lessons': []}, True) == COVERED_ELSEWHERE,
         '坏例24：覆盖表与园地证据的先后没定下来')

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
    garden_rules = json.loads(GARDEN_RULES.read_text(encoding='utf-8')).get('rulings', {}) if GARDEN_RULES.exists() else {}
    # 园地表（语文园地页里列出的篇名）只有一条来源（那个镜像），所以它只能决定「只有一条来源」这一档。
    # 篇名匹配用 check-textbook.py 的那一份（整名对、不许前缀互含）：归一化写两遍，迟早一遍认「悯农（其一）」一遍不认。
    import importlib.util
    _spec = importlib.util.spec_from_file_location('checktextbook', ROOT / 'tools' / 'check-textbook.py')
    CT = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(CT)
    garden_tbl = CT.load_garden()
    garden_same = set()
    if garden_tbl:
        for p in poems:
            for vol, _raw, _gn, _url in CT.garden_match(p, garden_tbl):
                if vol == p.get('volume'):
                    garden_same.add(p['id'])
    # 「课标篇目」还是「教材拓展」决定这一档长什么样：教材拓展的篇目不许冒领「课标要求」。
    # 口径从 validate.py 来，不在这里再抄一份课标表。
    _syllabus, extra_titles = V.parse_syllabus(V.SYLLABUS)
    extra_ids = {p['id'] for p in poems if V.canon_title(p['title']) in extra_titles}

    cov_problems = []
    for pid, cv in cov.items():
        if len(cv.get('sources') or []) < 2:
            cov_problems.append('%s 覆盖表里没写满两条独立来源' % pid)
        for l in cv['lessons']:
            if (l['volume'], l['title']) not in lesson_index and \
               (l['volume'], l.get('indexTitle') or '') not in lesson_index:
                cov_problems.append('textbook-coverage.json 里 %s 说教材有「%s」（%s），但教材目录表里找不到这一课' % (pid, l['title'], l['volume']))
    for pid, gr in garden_rules.items():
        ok, why = garden_rule_ok(gr, gr.get('volume') or '')
        if not ok and '仓内挂在' not in why:
            cov_problems.append('garden-rulings.json 里 %s 这条不成立：%s' % (pid, why))

    if cov_problems:
        # 以前这里调了一个不存在的 die()：覆盖表一有问题就 NameError 崩掉，
        # 看着像工具坏了，其实是把「哪一条是编的」这句话吞掉了。
        for x in cov_problems:
            print('  !! ' + x)
        return 1
    plan, unknown = [], []
    for p in poems:
        cv = cov.get(p['id'])
        gr = garden_rules.get(p['id'])
        gr_ok = bool(gr) and garden_rule_ok(gr, p.get('volume') or '')[0]
        st = status_with_coverage(by_id.get(p['id']), p.get('volume') or '', cv,
                                      p['id'] in garden_same,
                                      p['id'] not in extra_ids)
        st = status_with_garden(st, gr_ok)
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
        if cv or gr_ok:
            by = '；'.join(cover_label(l) for l in cv['lessons']) if cv else \
                 '%s%s' % (gr['volume'], gr.get('section') or '语文园地')
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
