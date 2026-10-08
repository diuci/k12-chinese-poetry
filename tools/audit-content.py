#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""内容整体审计：把「全、准、可核验」拆成一条条能跑的检查，出一份报告。



和别的工具的区别：

  validate.py 查格式与版权；check-text-sources 查正文真不真；build-ledger 数数。

  这个工具查的是「作为一个整体，这份内容能不能拿给孩子备考」——

  它不重复别人的活，它把别人的结论凑到一起，再补几条没人查的。



用法：

  python tools/audit-content.py            # 出 docs/audit.md

  python tools/audit-content.py --selftest # 坏例子必须被拦住

"""

import json

import re

import sys

from pathlib import Path



try:

    sys.stdout.reconfigure(encoding='utf-8')

except Exception:

    pass



ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / 'tools'))

import importlib.util







_bl_spec = importlib.util.spec_from_file_location('audit_ledger', ROOT / 'tools' / 'build-ledger.py')



_bl = importlib.util.module_from_spec(_bl_spec)



_bl_spec.loader.exec_module(_bl)



VM = _bl.VARIANT_MARK  # 「这条是不是异文」的唯一口径



SEC = ('全文', '必背全文')

REQUIRED = ('id', 'title', 'author', 'dynasty', 'license', 'source', 'stage', 'grade', 'volume', 'form')

CURRENT_YEAR = 2026





def sections(t):

    out = {}

    for m in re.finditer(r'^## ([^\r\n]+)\r?\n([\s\S]*?)(?=^## |\Z)', t, re.M):

        name = m.group(1).strip()

        out[name] = [x.strip() for x in m.group(2).splitlines() if x.strip() and not x.startswith('>')]

    return out





def body_of(c):

    """可背的正文：有 ## 全文 / ## 必背全文 就取它；没有就取 H1 之后、第一个 H2 之前

    （画、画鸡、稚子弄冰这类短诗没有 ## 全文，正文直接跟在标题后面）。"""

    parts = [c['sec'].get(s, []) for s in SEC]

    if any(parts):

        return '\n'.join(sum(parts, []))

    m = re.search(r'^#[^\n]*\n(?:>[^\n]*\n)*\n*([\s\S]*?)(?=^## |\Z)', c['text'], re.M)

    return m.group(1) if m else ''





def norm(s):

    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]', '', s)





def frontmatter(t):

    m = re.match(r'^---\r?\n([\s\S]*?)\r?\n---', t)

    if not m:

        return {}

    d = {}

    for line in m.group(1).splitlines():

        mm = re.match(r'^([A-Za-z][\w]*):\s*(.*)$', line.strip())

        if mm:

            d[mm.group(1)] = mm.group(2).strip().strip('"').strip("'")

    return d





def load_corpus():

    corpus = {}

    for p in sorted((ROOT / 'poems').rglob('*.md')):

        t = p.read_text(encoding='utf-8')

        fm = frontmatter(t)

        if 'id' not in fm:

            continue

        corpus[fm['id']] = {'id': fm['id'], 'path': p, 'title': fm.get('title', p.stem), 'fm': fm,

                            'text': t, 'sec': sections(t)}

    return corpus





def s2c_table():
    """简→繁 表（只用来判断「这个字是不是只有简体才用」）。"""
    f = ROOT / 'data' / 'opencc' / 'STCharacters.txt'
    tbl = {}
    if not f.exists():
        return tbl
    for line in f.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#') or '	' not in line:
            continue
        k, v = line.split('	', 1)
        if k.strip():
            tbl[k.strip()] = v.split()
    return tbl


def audit_trad(corpus, trad, trad_md, rows):
    """繁体产物的体检。

    不重复 build-traditional.py 的活（它自己会拒绝不合格的输出），
    这里查的是「繁体有没有覆盖每一篇、有没有把没依据的地方说成有依据」——
    繁体页面上线以后，这类问题不会再有别的工具发现。
    """
    out = []
    if trad is None:
        return [('繁体产物存在', False, 'data/traditional.json 不存在：繁体没派生，不许在页面上说有繁体版')]
    ids_ledger = {r['id'] for r in rows}
    ids_trad = {r['id'] for r in (trad.get('rows') or [])}
    miss = sorted(ids_ledger - ids_trad)
    extra = sorted(ids_trad - ids_ledger)
    out.append(('繁体派生覆盖每一篇', not miss and not extra,
                '台账 %d 篇，繁体 %d 篇；没派生 %d 篇，多出来 %d 篇'
                % (len(ids_ledger), len(ids_trad), len(miss), len(extra))))
    counts = trad.get('counts') or {}
    out.append(('繁体「一简对多繁」没有一处静默择一', counts.get('pending', -1) == 0,
                '待定 %d 处' % counts.get('pending', -1)))

    s2c = s2c_table()
    bad_chars = []
    for r in trad.get('rows') or []:
        c = corpus.get(r['id'])
        own = set(c['text']) if c else set()
        for seg in (r.get('text_trad') or []) + (r.get('lines_trad') or []):
            for ch in seg:
                if ch in s2c and ch not in s2c[ch] and ch not in own:
                    bad_chars.append('%s·%s' % (r['title'], ch))
                    break
    out.append(('繁体正文里没有只有简体才用的字', not bad_chars,
                '这样的字 %d 处%s' % (len(bad_chars),
                                      ('：' + '、'.join(bad_chars[:6])) if bad_chars else '')))

    rev = trad.get('reversal') or []
    unexplained = []
    copied = ruled = 0
    for x in rev:
        ours, tt, back = x.get('ours', ''), x.get('trad', ''), x.get('back', '')
        # 依据必须与正文对得上：写「照抄」就得真的没换字
        for b in (x.get('basis') or '').split('；'):
            if b == '照抄':
                copied += 1
                if len(ours) == len(tt) and len(ours) == len(back):
                    for k in range(len(ours)):
                        if ours[k] != back[k] and tt[k] == ours[k]:
                            break
                    else:
                        unexplained.append('%s·声称照抄但繁体换了字' % x.get('title', ''))
            elif b.startswith('裁定') or b.startswith('来源页'):
                ruled += 1
        unexplained += list(x.get('unexplained') or [])
    out.append(('可逆性不一致的每一处都说得出依据（照抄 / 裁定 / 页）', not unexplained,
                '不一致 %d 处：%d 处照抄本篇原有的字、%d 处有裁定或页依据；说不通的 %d 处%s'
                % (len(rev), copied, ruled, len(unexplained),
                   ('：' + '、'.join(unexplained[:5])) if unexplained else '')))

    # 注释 / 译文 / 赏析：台账说这篇有，繁体版就必须也有这一节
    need = {'hasNotes': '注释', 'hasTranslation': '译文', 'hasAppreciation': '赏析'}
    missing_sec = []
    have_sec = 0
    for r in (trad.get('rows') or []):
        row = {x['id']: x for x in rows}.get(r['id'])
        if not row:
            continue
        for k, name in need.items():
            if not row.get(k):
                continue
            if (r.get('sections_trad') or {}).get(name):
                have_sec += 1
            else:
                missing_sec.append('%s·%s' % (r['title'], name))
    out.append(('繁体版覆盖台账里有的每一节注释译文赏析', not missing_sec,
                '繁体派生出 %d 节；台账有、繁体没有的 %d 节%s'
                % (have_sec, len(missing_sec), ('：' + '、'.join(missing_sec[:5])) if missing_sec else '')))

    m = re.search(r'[|] pending [|] (\d+) [|]', trad_md or '')
    doc_pending = int(m.group(1)) if m else -1
    out.append(('繁体页面上的待定数与实际一致', doc_pending == counts.get('pending', -2),
                '页上写 %d 处，实际 %d 处' % (doc_pending, counts.get('pending', -2))))
    return out


def audit(corpus, ledger, tsrc, defects, trad=None, trad_md=None):

    """返回 [(检查名, 通过?, 说明)]。"""

    out = []

    ids = set(corpus)



    # 1 篇数：仓里的 md 与台账必须一模一样

    missing = sorted(set(r['id'] for r in ledger['rows']) - ids)

    extra = sorted(ids - set(r['id'] for r in ledger['rows']))

    out.append(('篇数一致', not missing and not extra,

                '仓内 %d 篇 / 台账 %d 行；台账里没有的 %d，仓里多出的 %d'

                % (len(corpus), len(ledger['rows']), len(missing), len(extra))))



    # 2 frontmatter 必填字段

    bad = [c['id'] for c in corpus.values() if any(k not in c['fm'] or not c['fm'][k] for k in REQUIRED)]

    out.append(('元信息必填项齐全', not bad, '缺的篇目：%d' % len(bad)))



    # 3 版权：作者卒年 + 50 必须已过期

    bad = []

    for c in corpus.values():

        fm = c['fm']

        y = fm.get('authorDied') or fm.get('authorEraEnd')

        try:

            y = int(y)

        except (TypeError, ValueError):

            bad.append(c['id']); continue

        if y > CURRENT_YEAR - 50:

            bad.append(c['id'])

    out.append(('版权口径（卒年+50）全部满足', not bad, '不满足的篇目：%d' % len(bad)))



    # 4 正文：每篇都得有可背的正文

    bad = [c['id'] for c in corpus.values()

           if not norm(body_of(c)) and not c['sec'].get('必背名句')]

    out.append(('每篇都有正文（全文或必背名句）', not bad,
                '缺的篇目：%d%s' % (len(bad), ('（' + '、'.join(bad[:6]) + '）') if bad else '')))



    # 5 注释 / 译文 / 赏析

    lack = []

    for c in corpus.values():

        for name in ('注释', '译文', '赏析'):

            if not c['sec'].get(name):

                lack.append('%s/%s' % (c['id'], name))

    out.append(('注释·译文·赏析 三样齐全', not lack, '缺的项：%d' % len(lack)))



    # 6 必背名句必须能在正文里找到（豁免只认 known-defects 登记的）

    exempt = set()

    for d in defects:

        k = d.get('key', '')

        if k.startswith('fullline:'):

            exempt.add(k.split(':', 1)[1])

    bad = []

    for c in corpus.values():

        if c['id'] in exempt:

            continue

        body = norm(body_of(c))

        if not body:

            continue

        for q in c['sec'].get('必背名句', []):

            if norm(q) and norm(q) not in body:

                bad.append(c['id']); break

    out.append(('必背名句与正文对得上', not bad, '对不上且没登记豁免的篇目：%d（已登记豁免 %d 篇）' % (len(bad), len(exempt))))



    # 7 节选/选修篇必须写明教材收在哪一课

    rows = {r['id']: r for r in ledger['rows']}

    bad = []

    for c in corpus.values():

        r = rows.get(c['id'], {})

        if r.get('stage') != '高中' or r.get('gaokaoGroup') != '选修':

            continue

        rng = c['sec'].get('收录范围') or []

        if not re.search(r'统编|教材|课标', '\n'.join(rng)):

            bad.append(c['id'])

    out.append(('选修（2026 起默写）篇写明教材出处', not bad, '没写明的篇目：%d' % len(bad)))



    # 8 出处核对：每篇都得有记录，而且记录不能是「跑挂了」

    recs = {r['id']: r for r in tsrc['results']}

    no_rec = sorted(ids - set(recs))

    errored = sorted(i for i, r in recs.items() if r.get('error'))

    nopage = sorted(i for i, r in recs.items() if i in ids and not r.get('page'))

    out.append(('每篇都有出处核对记录', not no_rec, '没有记录的篇目：%d' % len(no_rec)))

    out.append(('核对记录里没有「跑挂了」的', not errored, '带 error 的记录：%d（网络超时不是内容错误，必须重跑）' % len(errored)))

    out.append(('核对记录都找到了来源页', not nopage, '找不到来源页的篇目：%d' % len(nopage)))



    # 9 异文口径：自己按唯一口径重算一遍，和台账对

    # 条目切法必须和台账一样：按「换行 + - 」切块，只数以 - 开头的块。

    # 以前这里直接数小节里的每一行，把版权说明、校勘待办也算成异文，分母虚高。

    recount = {'total': 0, 'unverified': 0, 'non_variant': 0}

    for c in corpus.values():

        vtext = _bl.section_text(c['path'], '异文')

        entries = [x.strip() for x in re.split(r'\n(?=- )', vtext) if x.strip().startswith('- ')] if vtext else []

        real = [x for x in entries if VM.search(x)]

        recount['non_variant'] += len(entries) - len(real)

        recount['total'] += len(real)

        recount['unverified'] += sum(1 for x in real if '出处：仓内没核到' in x)

    g = ledger['summary']['gapCounts']

    same = (recount['total'] == g['异文条目总数']

            and recount['unverified'] == g['异文条目缺出处']

            and recount['non_variant'] == g['异文小节里的非异文条目'])

    out.append(('异文条目数与台账一致', same,

                '重算 条目 %d / 缺出处 %d / 非异文 %d；台账 %d / %d / %d'

                % (recount['total'], recount['unverified'], recount['non_variant'],

                   g['异文条目总数'], g['异文条目缺出处'], g['异文小节里的非异文条目'])))



    # 10 「仓内没核到」必须盖住全部缺出处条目——不许有连标签都没有的

    allv = '\n'.join('\n'.join(c['sec'].get('异文', [])) for c in corpus.values())



    labeled = allv.count('出处：仓内没核到')

    need = g['异文条目缺出处']

    out.append(('缺出处的异文全部写明「仓内没核到」', labeled >= need,

                '写明 %d 处 / 缺出处 %d 条' % (labeled, need)))



    # 11 台账自洽：出处核对四档相加必须等于篇数

    parts = [g['出处核对·逐句全对上'], g['出处核对·部分对上'], g['出处核对·一句都对不上'], g['出处核对·没有核对记录']]

    out.append(('出处核对四档相加等于篇数', sum(parts) == len(ledger['rows']),

                '%d + %d + %d + %d = %d，篇数 %d' % (parts[0], parts[1], parts[2], parts[3], sum(parts), len(ledger['rows']))))



    # 12 已知缺陷登记必须字段齐、口径合法

    bad = [d.get('key') for d in defects if not all(k in d for k in ('key', 'title', 'reason', 'phase', 'added'))

           or d.get('phase') not in ('正常', '口径')]

    out.append(('已知缺陷登记字段齐、phase 合法', not bad, '登记 %d 条，字段不对的 %d 条' % (len(defects), len(bad))))



    # 13 不许有没登记的重复副本

    dup = [r['id'] for r in ledger['rows'] if '与另一篇原文完全相同' in (r.get('flags') or [])]

    dup_reg = set()

    for d in defects:

        k = d.get('key', '')

        if k.startswith('duplicate:'):

            for part in k.split(':', 1)[1].split('|'):

                dup_reg.add(part.strip())

    unreg = [i for i in dup if i not in dup_reg]

    out.append(('重复副本全部登记在案', not unreg, '重复 %d 篇，没登记的 %d 篇' % (len(dup), len(unreg))))



    # 14 节选收录必须为零：只挂必背名句、没有正文的篇

    out.append(('没有「只有必背名句」的篇', g['只有必背名句（节选收录）'] == 0,

                '这样的篇 %d 篇' % g['只有必背名句（节选收录）']))

    out.append(('课标要求但仓内缺失为零', g['课标要求但仓内缺失'] == 0,

                '缺失 %d 篇' % g['课标要求但仓内缺失']))

    out.append(('来源不明为零', g['来源不明'] == 0, '来源不明 %d 篇' % g['来源不明']))

    out += audit_trad(corpus, trad, trad_md, ledger['rows'])
    return out





def selftest():

    bad = 0

    ledger = {'rows': [{'id': 'a'}, {'id': 'b'}],

              'summary': {'gapCounts': {'异文条目总数': 1, '异文条目缺出处': 0, '出处核对·逐句全对上': 1,

                                         '出处核对·部分对上': 1, '出处核对·一句都对不上': 0,

                                         '出处核对·没有核对记录': 0, '只有必背名句（节选收录）': 0,

                                         '课标要求但仓内缺失': 0, '来源不明': 0, '异文小节里的非异文条目': 0}}}

    tsrc = {'results': [{'id': 'a', 'page': 'X'}, {'id': 'b', 'page': 'Y'}]}

    base_fm = {'id': 'a', 'title': '甲', 'author': '佚名', 'dynasty': '唐', 'license': 'cc0',

               'source': 'S9', 'stage': '小学', 'grade': '一年级上', 'volume': '一上', 'form': '诗',

               'authorDied': '1600'}

    good = ('---\n' + '\n'.join('%s: %s' % (k, v) for k, v in base_fm.items()) + '\n---\n\n'

            '# 甲\n\n## 全文\n\n床前明月光，\n\n## 必背名句\n\n床前明月光，\n\n'

            '## 注释\n\n- 明月：明亮的月亮。\n\n## 译文\n\n明亮的月光。\n\n'

            '## 赏析\n\n写的是月光。\n\n## 异文\n\n- 明月：一作「明山」，出自《全唐文》，取「明月」。\n')

    fm2 = dict(base_fm); fm2['id'] = 'b'

    good_b = ('---\n' + '\n'.join('%s: %s' % (k, v) for k, v in fm2.items()) + '\n---\n\n'

              '# 乙\n\n## 全文\n\n处处闻啼鸟，\n\n## 注释\n\n- 处处：到处。\n\n'

              '## 译文\n\n到处听到鸟叫。\n\n## 赏析\n\n写的是早晨。\n')

    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix='audit-selftest-'))

    def corpus_of(a_text, b_text):
        c = {}
        for txt, pid in ((a_text, 'a'), (b_text, 'b')):
            fp = tmp / (pid + '.md')
            fp.write_text(txt, encoding='utf-8', newline='\n')
            c[pid] = {'id': pid, 'path': fp, 'title': pid, 'fm': frontmatter(txt),
                      'text': txt, 'sec': sections(txt)}
        return c



    TRAD_GOOD = {'counts': {'page': 2, 'table': 1, 'rule': 0, 'keep': 0, 'identity': 3,
                            'variant': 0, 'pending': 0},
                 'reversal': [],
                 'rows': [{'id': 'a', 'title': '甲', 'text_trad': ['床前明月光，'], 'lines_trad': []},
                          {'id': 'b', 'title': '乙', 'text_trad': ['處處聞啼鳥，'], 'lines_trad': []}]}
    MD_GOOD = '| pending | 0 | 没依据 —— 待定，不许当成已定 |'

    def fails(corpus, ledger_, tsrc_, defects_, names):

        res = audit(corpus, ledger_, tsrc_, defects_, TRAD_GOOD, MD_GOOD)

        got = {n for n, ok, _ in res if not ok}

        return got



    # 1) 全绿基线：不该有任何一条被报

    c0 = corpus_of(good, good_b)

    got = fails(c0, ledger, tsrc, [{'key': 'duplicate:x|y', 'title': 'x', 'reason': 'r', 'phase': '口径', 'added': '2026-01-01'}], [])

    got.discard('重复副本全部登记在案')  # 基线里没有重复篇

    got.discard('异文条数与台账一致')

    if got:

        print('坏例1：全绿的样本被报了 %s' % '、'.join(sorted(got))); bad += 1

    # 2) 缺译文必须被报

    c = corpus_of(good.replace('## 译文\n\n明亮的月光。\n\n', ''), good_b)

    if '注释·译文·赏析 三样齐全' not in fails(c, ledger, tsrc, [], []):

        print('坏例2：缺译文的篇没被报'); bad += 1

    # 3) 卒年太晚必须被拦

    late = good.replace('authorDied: 1600', 'authorDied: 1980')

    c = corpus_of(late, good_b)

    if '版权口径（卒年+50）全部满足' not in fails(c, ledger, tsrc, [], []):

        print('坏例3：1980 年卒的作者没被拦'); bad += 1

    # 4) 必背名句不在正文里、又没登记豁免，必须被报

    fake = good.replace('## 必背名句\n\n床前明月光，', '## 必背名句\n\n床前山色好，')

    c = corpus_of(fake, good_b)

    if '必背名句与正文对得上' not in fails(c, ledger, tsrc, [], []):

        print('坏例4：假必背名句没被报'); bad += 1

    # 5) 核对记录里带 error（跑挂了）必须被报

    t2 = {'results': [{'id': 'a', 'page': 'X', 'error': 'TimeoutError'}, {'id': 'b', 'page': 'Y'}]}

    if '核对记录里没有「跑挂了」的' not in fails(c0, ledger, t2, [], []):

        print('坏例5：跑挂的记录被当成正常'); bad += 1

    # 6) 出处核对四档相加不等于篇数，必须被报

    l2 = json.loads(json.dumps(ledger)); l2['summary']['gapCounts']['出处核对·逐句全对上'] = 5

    if '出处核对四档相加等于篇数' not in fails(c0, l2, tsrc, [], []):

        print('坏例6：台账数字不自洽没被报'); bad += 1

    # 7) 元信息缺 license 必须被报

    c = corpus_of(good.replace('license: cc0', 'license:'), good_b)

    if '元信息必填项齐全' not in fails(c, ledger, tsrc, [], []):

        print('坏例7：缺 license 没被报'); bad += 1

    # 8) 缺出处却没写「仓内没核到」，必须被报

    l3 = json.loads(json.dumps(ledger)); l3['summary']['gapCounts']['异文条目缺出处'] = 9

    if '缺出处的异文全部写明「仓内没核到」' not in fails(c0, l3, tsrc, [], []):

        print('坏例8：缺出处条数超过标签数没被报'); bad += 1

    # 9) 短诗没有 ## 全文，正文直接跟在标题后——不许被报成「没正文」

    short = good.replace('## 全文\n\n床前明月光，\n\n', '')

    short = short.replace('# 甲\n\n', '# 甲\n\n床前明月光，\n\n')

    c = corpus_of(short, good_b)

    if '每篇都有正文（全文或必背名句）' in fails(c, ledger, tsrc, [], []):

        print('坏例9：短诗的正文没抽到，被误报成没正文'); bad += 1

    # 10) 繁体漏了篇，必须被报
    t10 = {'counts': dict(TRAD_GOOD['counts']), 'reversal': [],
           'rows': [r for r in TRAD_GOOD['rows'] if r['id'] == 'a']}
    got10 = {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t10, MD_GOOD) if not ok}
    if '繁体派生覆盖每一篇' not in got10:
        print('坏例10：繁体漏篇没被报；实际报的是 ' + ('、'.join(sorted(got10)) or '（什么都没报）')); bad += 1
    # 11) 繁体有静默择一的待定处，必须被报
    t11 = {'counts': dict(TRAD_GOOD['counts', ] if False else TRAD_GOOD['counts']), 'reversal': [],
           'rows': TRAD_GOOD['rows']}
    t11['counts']['pending'] = 3
    if '繁体「一简对多繁」没有一处静默择一' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t11, MD_GOOD) if not ok}:
        print('坏例11：繁体待定 3 处没被报'); bad += 1
    # 12) 繁体正文里留下只有简体才用的字，必须被报
    t12 = {'counts': dict(TRAD_GOOD['counts']), 'reversal': [],
           'rows': [dict(r) for r in TRAD_GOOD['rows']]}
    t12['rows'][1]['text_trad'] = ['處處聞啼鳥，體格。']
    t12['rows'][1]['lines_trad'] = ['身体。']
    if '繁体正文里没有只有简体才用的字' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t12, MD_GOOD) if not ok}:
        print('坏例12：繁体正文里的简体字「体」没被拦'); bad += 1
    # 12b) 台账说这篇有译文，繁体版却没派生这一节，必须被报
    t12b = {'counts': dict(TRAD_GOOD['counts']), 'reversal': [],
            'rows': [dict(r) for r in TRAD_GOOD['rows']]}
    led2 = {'rows': [dict(r) for r in ledger['rows']]}
    led2['rows'][1]['hasTranslation'] = True
    led2['summary'] = ledger['summary']
    t12b['rows'][1]['sections_trad'] = {'注释': ['處處聞啼鳥。']}
    if '繁体版覆盖台账里有的每一节注释译文赏析' not in {nm for nm, ok, _ in audit(c0, led2, tsrc, [], t12b, MD_GOOD) if not ok}:
        print('坏例12b：繁体漏了译文这一节没被报'); bad += 1
    # 13) 页上写的待定数与实际不符，必须被报
    if '繁体页面上的待定数与实际一致' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t11, MD_GOOD) if not ok}:
        print('坏例13：页上 pending 0、实际 3，没被报'); bad += 1
    # 14) 可逆性不一致却说不通（繁体没照抄我们正文里的字），必须被报
    t14 = {'counts': dict(TRAD_GOOD['counts']), 'rows': TRAD_GOOD['rows'],
           'reversal': [{'id': 'a', 'title': '甲', 'field': 'full', 'line': 0,
                         'ours': '床前明月光，', 'trad': '床前明山光，', 'back': '床前明山光，',
                         'chars': '月→山', 'basis': '（说不通）', 'unexplained': ['甲·月']}]}
    if '可逆性不一致的每一处都说得出依据（照抄 / 裁定 / 页）' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t14, MD_GOOD) if not ok}:
        print('坏例14：繁体把正文的字换掉了却没给依据，没被报'); bad += 1
    # 坏例14b：依据写「照抄」但繁体其实换了字，必须被报
    t14b = {'counts': dict(TRAD_GOOD['counts']), 'rows': TRAD_GOOD['rows'],
            'reversal': [{'id': 'a', 'title': '甲', 'field': 'full', 'line': 0,
                          'ours': '床前明月光，', 'trad': '床前明山光，', 'back': '床前明山光，',
                          'chars': '月→山', 'basis': '照抄', 'unexplained': []}]}
    if '可逆性不一致的每一处都说得出依据（照抄 / 裁定 / 页）' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t14b, MD_GOOD) if not ok}:
        print('坏例14b：谎称照抄没被报'); bad += 1
    # 15) 繁体产物不存在，必须被报（不许「没跑成」长得像「没问题」）
    if '繁体产物存在' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], None, None) if not ok}:
        print('坏例15：繁体产物不存在却没被报'); bad += 1

    if bad:

        print('[!] audit-content --selftest 失败 %d 项' % bad)

        return 1

    print('[ok] audit-content --selftest 通（17 个坏例子全部试到）')

    return 0





def main():

    if '--selftest' in sys.argv:

        return selftest()

    corpus = load_corpus()

    ledger = json.loads((ROOT / 'data' / 'ledger.json').read_text(encoding='utf-8'))

    tsrc = json.loads((ROOT / 'data' / 'text-sources.json').read_text(encoding='utf-8'))

    defects = json.loads((ROOT / 'data' / 'known-defects.json').read_text(encoding='utf-8'))

    if isinstance(defects, dict):

        defects = defects.get('defects', [])

    tj = ROOT / 'data' / 'traditional.json'
    trad = json.loads(tj.read_text(encoding='utf-8')) if tj.exists() else None
    mj = ROOT / 'docs' / 'traditional.md'
    trad_md = mj.read_text(encoding='utf-8') if mj.exists() else ''
    res = audit(corpus, ledger, tsrc, defects, trad, trad_md)

    g = ledger['summary']['gapCounts']

    lines = ['# 内容整体审计', '',

             '这份报告不是「格式对不对」，是「这份内容能不能拿给孩子备考」。',

             '每一条都是脚本跑出来的，不是手写的说法。', '',

             '## 检查清单', '', '| 检查 | 结果 | 数字 |', '| --- | --- | --- |']

    for name, ok, detail in res:

        lines.append('| %s | %s | %s |' % (name, '通过' if ok else '**没通过**', detail))

    lines += ['', '## 当前数字', '',

              '- 篇数：%d' % len(ledger['rows']),

              '- 有全文正文：%d；只有必背名句：%d' % (g['仓内有全文正文'], g['只有必背名句（节选收录）']),

              '- 出处核对：逐句全对上 %d / 部分对上 %d / 一句都对不上 %d / 没有核对记录 %d'

              % (g['出处核对·逐句全对上'], g['出处核对·部分对上'], g['出处核对·一句都对不上'], g['出处核对·没有核对记录']),

              '- 异文条目：%d（带出处 %d / 带取舍 %d / 缺出处 %d）' % (g['异文条目总数'], g['异文条目带出处'], g['异文条目带取舍'], g['异文条目缺出处']),

              '- 已知缺陷登记：%d 条' % len(defects),

              '', '本文件由 tools/audit-content.py 生成，不要手改。', '']

    (ROOT / 'docs' / 'audit.md').write_text('\n'.join(lines), encoding='utf-8')

    n_bad = sum(1 for _, ok, _ in res if not ok)

    print('[审计] 检查 %d 项，没通过 %d 项；报告 docs/audit.md' % (len(res), n_bad))

    for name, ok, detail in res:

        if not ok:

            print('   没通过：%s —— %s' % (name, detail))

    return 1 if n_bad else 0





if __name__ == '__main__':

    sys.exit(main())

