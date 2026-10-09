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
REV_EXC = ROOT / 'data' / 'reversal-exceptions.json'
REV_EXC_TEST = None   # 自检专用：换一份登记表来试坏例子，仓里那份不动

sys.path.insert(0, str(ROOT / 'tools'))

import importlib.util







_bl_spec = importlib.util.spec_from_file_location('audit_ledger', ROOT / 'tools' / 'build-ledger.py')



_bl = importlib.util.module_from_spec(_bl_spec)



_bl_spec.loader.exec_module(_bl)



VM = _bl.VARIANT_MARK  # 「这条是不是异文」的唯一口径



SEC = ('全文', '必背全文')

REQUIRED = ('id', 'title', 'author', 'dynasty', 'license', 'source', 'stage', 'grade', 'volume', 'form')

CURRENT_YEAR = 2026





def reversal_registry():
    """可逆性例外的登记表（data/reversal-exceptions.json）。自检可换一份（REV_EXC_TEST），仓里那份不动。"""
    p = REV_EXC_TEST or REV_EXC
    try:
        entries = json.loads(p.read_text(encoding='utf-8')).get('entries') or []
    except Exception as e:
        return set(), '读不到 %s：%s' % (p, e)
    reg = set()
    for e in entries:
        reg.add((e.get('id'), e.get('simp'), e.get('trad'), e.get('back')))
    return reg, None

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

    # 标题与作者也是页面上要显示的字：缺了就是繁体页顶上写着简体
    no_label = [r['title'] for r in (trad.get('rows') or [])
                if not (r.get('labels_trad') or {}).get('title')
                or not (r.get('labels_trad') or {}).get('author')]
    out.append(('繁体版有繁体标题与繁体作者', not no_label,
                '缺繁体标题或作者的 %d 篇%s'
                % (len(no_label), ('：' + '、'.join(no_label[:5])) if no_label else '')))
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

    # 繁体文本（正文 + 各节 + 标签）里残留的简体专用字：每一处都要在 left_behind 里说得出凭什么。
    # 派生工具自己会拦这一处；这里拦的是「产物被人手改过」或「工具换了却没重跑」。
    simp_only = {k for k, v in s2c.items() if k not in v}
    unjust = []
    for r in trad.get('rows') or []:
        texts = list(r.get('text_trad') or []) + list(r.get('lines_trad') or [])
        for _v in (r.get('sections_trad') or {}).values():
            texts.extend(_v)
        for _v in (r.get('labels_trad') or {}).values():
            texts.extend(_v if isinstance(_v, list) else [_v])
        allowed = {x.get('char') for x in (r.get('left_behind') or [])
                   if isinstance(x, dict) and (x.get('why') or '').strip()}
        for txt in texts:
            for ch in txt:
                if ch in simp_only and ch not in allowed:
                    unjust.append('%s·%s' % (r.get('title'), ch))
                    break
    out.append(('繁体文本残留的简体专用字每一处都写了依据', not unjust,
                '没说凭什么 %d 处%s' % (len(unjust),
                                        ('：' + '、'.join(sorted(set(unjust))[:6])) if unjust else '')))

    rev = trad.get('reversal') or []
    unexplained = []
    copied = ruled = registered = 0
    trip = set()
    for x in rev:
        ours, tt, back = x.get('ours', ''), x.get('trad', ''), x.get('back', '')
        diff = [k for k in range(min(len(ours), len(back))) if ours[k] != back[k]]
        for k in diff:
            trip.add((x.get('id'), ours[k], tt[k] if k < len(tt) else '', back[k]))
        # 依据必须与正文对得上：说「正文本来就写作这个字」就得真的没换字。
        # 按「这一行」归类，不按分号切开的片段归类——登记理由里本来就常写「来源页作某字」，
        # 切片段会把一条登记数成两处依据，数目看着对其实不对。
        b_all = x.get('basis') or ''
        if '登记例外' in b_all:
            registered += 1
            if '（正文本来就写作这个字）' in b_all:
                if not any(k < len(tt) and tt[k] == ours[k] for k in diff):
                    unexplained.append('%s·登记说正文原字，繁体却换了字' % x.get('title', ''))
            elif not any(k >= len(tt) or tt[k] != ours[k] for k in diff):
                unexplained.append('%s·登记说有意换字，繁体其实没换' % x.get('title', ''))
        elif '照抄' in b_all:
            copied += 1
            if not any(k < len(tt) and tt[k] == ours[k] for k in diff):
                unexplained.append('%s·声称照抄但繁体换了字' % x.get('title', ''))
        elif '裁定' in b_all or '来源页' in b_all:
            ruled += 1
        unexplained += list(x.get('unexplained') or [])
    out.append(('可逆性不一致的每一处都说得出依据（照抄 / 裁定 / 页 / 登记例外）', not unexplained,
                '不一致 %d 处：%d 处照抄本篇原有的字、%d 处有裁定或页依据、%d 处登记例外；说不通的 %d 处%s'
                % (len(rev), copied, ruled, registered, len(unexplained),
                   ('：' + '、'.join(unexplained[:5])) if unexplained else '')))
    reg, err = reversal_registry()
    if err:
        out.append(('可逆性不一致的每一处都在登记表里登记过', False, err))
    else:
        gap = sorted('/'.join(str(p) for p in k) for k in (reg - trip) | (trip - reg))
        out.append(('可逆性不一致的每一处都在登记表里登记过', not gap,
                    '产物里 %d 处不同、登记表 %d 条；对不上 %d 条%s'
                    % (len(trip), len(reg), len(gap), ('：' + '、'.join(gap[:6])) if gap else '')))

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


def split_nopage(recs, ids):
    """把「没有来源页」拆成两种：搜过并写明的，和没交代的。

    只有 no_page=True、note（override）非空、searched 非空三样凑齐，才算「核过确实没有」。
    少任何一样都算没交代——空过的检查比没有检查更危险。
    """
    all_np = sorted(i for i, r in recs.items() if i in ids and not r.get('page'))
    unexplained = []
    for i in all_np:
        r = recs[i]
        if r.get('no_page') and (r.get('override') or '').strip() and (r.get('searched') or []):
            continue
        unexplained.append(i)
    return all_np, unexplained


def doc_number_claims(doc_text, actuals):
    """文档里写死的数字，必须与当场算出来的对得上。

    写死的数字会过期，而过期的数字比没有数字更危险：它让人以为这一处已经数过了。
    本轮就是这么抓出来的——accuracy.md 写着「裁定表里有 8 条规则管着『里』」，
    当场数 `data/s2t-rules.json`：「里」只有 2 条。
    """
    bad = []
    for pat, want in actuals.items():
        for m in re.finditer(pat, doc_text or ''):
            got = int(m.group(1))
            if got != want:
                bad.append('「%s」写 %d，实际 %d' % (m.group(0).strip(), got, want))
    return bad


def count_ci_selftests(yml_text):
    """CI 里真正跑了多少项自检：只数 workflow 里那一行行命令，不数说明文字里提到的 `--selftest`。

    文档写「CI 有 N 项自检」时，N 必须由这份 workflow 当场数出来——
    否则「加了检查」这句话可以一直写在文档里，而 workflow 里那一行早就被人删了。
    """
    n = 0
    for ln in (yml_text or '').splitlines():
        if re.match(r'^\s+(python3|node) tools/\S+ --selftest\s*$', ln):
            n += 1
    return n


def count_ci_block(yml_text, name_prefix):
    """数 workflow 里某个 `run: |` 块真正执行的命令行数（注释与空行不算）。

    文档写「CI 有 N 项离线检查」时，N 必须由这份 workflow 数出来——
    否则有人从块里删掉一行，文档里那句「13 项」还能再活一年。
    """
    lines = (yml_text or '').splitlines()
    i = 0
    while i < len(lines):
        if re.match(r'^\s*- name:\s*' + re.escape(name_prefix), lines[i]):
            j = i + 1
            while j < len(lines) and not re.match(r'^\s*run:\s*\|', lines[j]):
                if re.match(r'^\s*- name:', lines[j]):
                    return 0
                j += 1
            if j >= len(lines) or not re.match(r'^\s*run:\s*\|', lines[j]):
                return 0
            base = len(lines[j]) - len(lines[j].lstrip())
            n = 0
            k = j + 1
            while k < len(lines):
                cur = lines[k]
                if not cur.strip():
                    k += 1
                    continue
                if len(cur) - len(cur.lstrip()) <= base:
                    break
                if not cur.lstrip().startswith('#'):
                    n += 1
                k += 1
            return n
        i += 1
    return 0


def audit(corpus, ledger, tsrc, defects, trad=None, trad_md=None, accuracy_md=None, verify_yml=None):

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

    nopage_all, nopage = split_nopage(recs, ids)

    out.append(('每篇都有出处核对记录', not no_rec, '没有记录的篇目：%d' % len(no_rec)))

    out.append(('核对记录里没有「跑挂了」的', not errored, '带 error 的记录：%d（网络超时不是内容错误，必须重跑）' % len(errored)))

    # 「没有来源页」有两种，字段看起来一样：一种搜过、确实没有正文页；一种没核到或没去核。
    # 把两种算成一笔账，等于允许后一种混过去。
    explained = sorted(set(nopage_all) - set(nopage))
    out.append(('没有来源页的都必须写明搜过什么', not nopage,
                '没交代就记「没有来源页」的篇目：%d；搜过并写明的 %d 篇（%s）'
                % (len(nopage), len(explained), '、'.join(explained) or '无')))



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



    # 11 台账自洽：出处核对各档相加必须等于篇数。
    # 档名由台账定，这里不许写死档名——台账加一档（比如「核过没有正文页」），
    # 写死档名的检查就会悄悄少算一档，然后一直「通过」。
    keys = sorted(k for k in g if k.startswith('出处核对·'))
    total = sum(g[k] for k in keys)
    out.append(('出处核对各档相加等于篇数', total == len(ledger['rows']),
                ' / '.join('%s %d' % (k.split('·', 1)[1], g[k]) for k in keys) +
                ' = %d，篇数 %d' % (total, len(ledger['rows']))))



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

    # 文档里写死的数字：过期了就是说假话。这一项盯裁定表条数、CI 的两块命令数、派生计数的四个数。
    sp = ROOT / 'data' / 's2t-rules.json'
    s2t_total = len(json.loads(sp.read_text(encoding='utf-8')).get('rules', [])) if sp.exists() else -1
    ci_selftests = count_ci_selftests(verify_yml)
    ci_offline = count_ci_block(verify_yml, '离线检查')
    actuals = {r'裁定表\s*(\d+)\s*条': s2t_total,
               r'(\d+)\s*项检查器自检': ci_selftests,
               r'(\d+)\s*项离线检查': ci_offline}
    ca = (trad or {}).get('counts_apparatus') or {}
    if ca:
        actuals.update({r'按表\s*(\d+)': ca.get('table', -1),
                        r'按裁定表\s*(\d+)': ca.get('rule', -1),
                        r'照表原字\s*(\d+)': ca.get('identity', -1),
                        r'保留\s*(\d+)': ca.get('keep', -1),
                        r'待定\s*(\d+)': ca.get('pending', -1)})
    # 出处核对的四档数字：文档里那句「N 全对上 / M 部分…」必须与 data/text-sources.json 当场一致。
    # 这一轮 --refresh 之后有一篇从「全对上」挪进「部分对上」，文档没跟着改，就是靠这一条抓的。
    tstats = (tsrc or {}).get('stats') or {}
    if tstats:
        actuals.update({r'(\d+)\s*全对上': tstats.get('attested', -1),
                        r'(\d+)\s*部分对上': tstats.get('partial', -1),
                        r'(\d+)\s*一句都对不上': tstats.get('notfound', -1),
                        r'(\d+)\s*核过没有正文页': tstats.get('nosource', -1)})
    claims = doc_number_claims(accuracy_md or '', actuals)
    out.append(('文档里写死的数字与产物一致', not claims,
                '当场数：裁定表 %d 条、CI 自检 %d 项、CI 离线 %d 项、出处核对 %s、apparatus %s；%s'
                % (s2t_total, ci_selftests, ci_offline,
                   json.dumps(tstats, ensure_ascii=False) if tstats else '（这次没带出处核对统计）',
                   json.dumps(ca, ensure_ascii=False) if ca else '（这次没带 apparatus）',
                   '；'.join(claims) if claims else '文档里的数字全对得上')))

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

    # 可逆性登记表：自检换一份空的（TRAD_GOOD 里没有可逆性不一致），仓里那一份不动
    global REV_EXC_TEST
    REV_EXC_TEST = tmp / 'reversal-exceptions-empty.json'
    REV_EXC_TEST.write_text(json.dumps({'entries': []}, ensure_ascii=False), encoding='utf-8')

    def rev_reg(name, entries):
        p = tmp / name
        p.write_text(json.dumps({'entries': entries}, ensure_ascii=False), encoding='utf-8')
        return p

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
                 'rows': [{'id': 'a', 'title': '甲', 'text_trad': ['床前明月光，'], 'lines_trad': [],
                           'labels_trad': {'title': '甲', 'author': '李'},
                           'left_behind': [{'char': '床', 'why': '正文自己写作这个形'}]},
                          {'id': 'b', 'title': '乙', 'text_trad': ['處處聞啼鳥，'], 'lines_trad': [],
                           'labels_trad': {'title': '乙', 'author': '孟浩然'}}]}
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

    # 6) 出处核对各档相加不等于篇数，必须被报

    l2 = json.loads(json.dumps(ledger)); l2['summary']['gapCounts']['出处核对·逐句全对上'] = 5

    if '出处核对各档相加等于篇数' not in fails(c0, l2, tsrc, [], []):

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
    # 12d) 繁体某一节里留下只有简体才用的字，却没写依据：必须被报
    t12d = {'counts': dict(TRAD_GOOD['counts']), 'reversal': [],
            'rows': [dict(r) for r in TRAD_GOOD['rows']]}
    t12d['rows'][1]['sections_trad'] = {'译文': ['这个。']}
    if '繁体文本残留的简体专用字每一处都写了依据' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t12d, MD_GOOD) if not ok}:
        print('坏例12d：繁体译文里的简体字「这」没有依据却没被拦'); bad += 1
    # 12e) 同一处写了依据，就不许再被报（护栏不许只会喊）
    t12e = {'counts': dict(TRAD_GOOD['counts']), 'reversal': [],
            'rows': [dict(r) for r in TRAD_GOOD['rows']]}
    t12e['rows'][1]['sections_trad'] = {'译文': ['这个。']}
    t12e['rows'][1]['left_behind'] = [{'char': '这', 'why': '引文：这一处引的是别本写法'},
                                 {'char': '个', 'why': '引文：这一处引的是别本写法'}]
    if '繁体文本残留的简体专用字每一处都写了依据' in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t12e, MD_GOOD) if not ok}:
        print('坏例12e：写了依据还被报'); bad += 1
    # 12b) 台账说这篇有译文，繁体版却没派生这一节，必须被报
    t12b = {'counts': dict(TRAD_GOOD['counts']), 'reversal': [],
            'rows': [dict(r) for r in TRAD_GOOD['rows']]}
    led2 = {'rows': [dict(r) for r in ledger['rows']]}
    led2['rows'][1]['hasTranslation'] = True
    led2['summary'] = ledger['summary']
    t12b['rows'][1]['sections_trad'] = {'注释': ['處處聞啼鳥。']}
    if '繁体版覆盖台账里有的每一节注释译文赏析' not in {nm for nm, ok, _ in audit(c0, led2, tsrc, [], t12b, MD_GOOD) if not ok}:
        print('坏例12b：繁体漏了译文这一节没被报'); bad += 1
    # 12c) 繁体页顶上写着简体标题/作者，必须被报
    t12c = {'counts': dict(TRAD_GOOD['counts']), 'reversal': [],
            'rows': [dict(r) for r in TRAD_GOOD['rows']]}
    t12c['rows'][1]['labels_trad'] = {'title': '乙'}
    if '繁体版有繁体标题与繁体作者' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t12c, MD_GOOD) if not ok}:
        print('坏例12c：繁体缺作者没被报'); bad += 1
    # 13) 页上写的待定数与实际不符，必须被报
    if '繁体页面上的待定数与实际一致' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t11, MD_GOOD) if not ok}:
        print('坏例13：页上 pending 0、实际 3，没被报'); bad += 1
    # 14) 可逆性不一致却说不通（繁体没照抄我们正文里的字），必须被报
    t14 = {'counts': dict(TRAD_GOOD['counts']), 'rows': TRAD_GOOD['rows'],
           'reversal': [{'id': 'a', 'title': '甲', 'field': 'full', 'line': 0,
                         'ours': '床前明月光，', 'trad': '床前明山光，', 'back': '床前明山光，',
                         'chars': '月→山', 'basis': '（说不通）', 'unexplained': ['甲·月']}]}
    if '可逆性不一致的每一处都说得出依据（照抄 / 裁定 / 页 / 登记例外）' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t14, MD_GOOD) if not ok}:
        print('坏例14：繁体把正文的字换掉了却没给依据，没被报'); bad += 1
    # 坏例14b：依据写「照抄」但繁体其实换了字，必须被报
    t14b = {'counts': dict(TRAD_GOOD['counts']), 'rows': TRAD_GOOD['rows'],
            'reversal': [{'id': 'a', 'title': '甲', 'field': 'full', 'line': 0,
                          'ours': '床前明月光，', 'trad': '床前明山光，', 'back': '床前明山光，',
                          'chars': '月→山', 'basis': '照抄', 'unexplained': []}]}
    if '可逆性不一致的每一处都说得出依据（照抄 / 裁定 / 页 / 登记例外）' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t14b, MD_GOOD) if not ok}:
        print('坏例14b：谎称照抄没被报'); bad += 1
    # 坏例14c：产物里有一处可逆性不一致没登记，必须被报
    t14c = {'counts': dict(TRAD_GOOD['counts']), 'rows': TRAD_GOOD['rows'],
            'reversal': [{'id': 'a', 'title': '甲', 'field': 'full', 'line': 0,
                          'ours': '床前明月光，', 'trad': '床前明月光，', 'back': '床前明山光，',
                          'chars': '月→山', 'basis': '登记例外（正文本来就写作这个字）：表有损', 'unexplained': []}]}
    REV_EXC_TEST = rev_reg('rev-empty.json', [])
    if '可逆性不一致的每一处都在登记表里登记过' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t14c, MD_GOOD) if not ok}:
        print('坏例14c：可逆性不一致没登记也照样过'); bad += 1
    # 坏例14d：登记表里多一条这一轮没用上的，必须被报（过期登记比没有登记更误导人）
    REV_EXC_TEST = rev_reg('rev-extra.json', [
        {'id': 'a', 'simp': '月', 'trad': '月', 'back': '山', 'why': '表有损', 'basis': '正文原字'}])
    if '可逆性不一致的每一处都在登记表里登记过' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], TRAD_GOOD, MD_GOOD) if not ok}:
        print('坏例14d：登记表多一条没用上的也没人管'); bad += 1
    # 坏例14e：登记与产物严丝合缝——这一处不许误报（好例子被误报也算失败）
    REV_EXC_TEST = rev_reg('rev-match.json', [
        {'id': 'a', 'simp': '月', 'trad': '月', 'back': '山', 'why': '表有损', 'basis': '正文原字'}])
    t14e = {'counts': dict(TRAD_GOOD['counts']), 'rows': TRAD_GOOD['rows'],
            'reversal': [{'id': 'a', 'title': '甲', 'field': 'full', 'line': 0,
                          'ours': '床前明月光，', 'trad': '床前明月光，', 'back': '床前明山光，',
                          'chars': '月→山', 'basis': '登记例外（正文本来就写作这个字）：表有损', 'unexplained': []}]}
    if '可逆性不一致的每一处都在登记表里登记过' in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], t14e, MD_GOOD) if not ok}:
        print('坏例14e：登记与产物一致却被误报'); bad += 1
    REV_EXC_TEST = REV_EXC   # 自检换的登记表到此为止
    # 15) 繁体产物不存在，必须被报（不许「没跑成」长得像「没问题」）
    if '繁体产物存在' not in {nm for nm, ok, _ in audit(c0, ledger, tsrc, [], None, None) if not ok}:
        print('坏例15：繁体产物不存在却没被报'); bad += 1

    # 16) 「没有来源页」必须分两种：搜过并写明的放行，没交代的必须报
    fake = {'a': {'id': 'a', 'page': None, 'no_page': True, 'override': '搜过六个串都没有',
                  'searched': ['頭上紅冠不用裁']},
            'b': {'id': 'b', 'page': None},
            'c': {'id': 'c', 'page': None, 'no_page': True, 'override': '', 'searched': ['x']},
            'd': {'id': 'd', 'page': None, 'no_page': True, 'override': '搜过', 'searched': []}}
    allnp, badnp = split_nopage(fake, {'a', 'b', 'c', 'd'})
    if allnp != ['a', 'b', 'c', 'd']:
        print('坏例16：没有来源页的篇目没数全'); bad += 1
    if badnp != ['b', 'c', 'd']:
        print('坏例16b：没交代的「没有来源页」被放行了'); bad += 1

    # 17) 文档里写死的数字过期了必须被报；对得上不许误伤；没写数字也不许报
    pat = {r'裁定表\s*(\d+)\s*条': 102}
    if not doc_number_claims('裁定表 99 条规则管着「里」', pat):
        print('坏例17：文档写「裁定表 99 条」而表是 102 条，没被报'); bad += 1
    if doc_number_claims('裁定表 102 条规则', pat):
        print('坏例17b：数字对得上却被报了'); bad += 1
    if doc_number_claims('条数见 data/s2t-rules.json，不在这里写死', pat):
        print('坏例17c：文档没写数字却被报了'); bad += 1
    if len(doc_number_claims('裁定表 99 条，另有裁定表 105 条', pat)) != 2:
        print('坏例17d：同一份文档里两处过期数字只报了一处'); bad += 1
    # 坏例17e：文档写「CI 有 N 项自检」，N 必须由 workflow 当场数出来
    yml = ('        run: |\n          python3 tools/validate.py --selftest\n'
           '          node tools/check-legal.mjs --selftest\n'
           '      - name: 说明\n        run: echo "上面每一项都带 --selftest"\n')
    if count_ci_selftests(yml) != 2:
        print('坏例17e：CI 自检项数数错了（算出 %d，应当 2——说明文字里提到的不算）' % count_ci_selftests(yml)); bad += 1
    if count_ci_selftests('') != 0:
        print('坏例17f：没有 workflow 却被数出了自检项'); bad += 1
    if not doc_number_claims('CI 有 3 项检查器自检', {r'(\d+)\s*项检查器自检': count_ci_selftests(yml)}):
        print('坏例17g：文档写「3 项」而 workflow 里只有 2 项，没被报'); bad += 1
    if doc_number_claims('CI 有 2 项检查器自检', {r'(\d+)\s*项检查器自检': count_ci_selftests(yml)}):
        print('坏例17h：文档数字对得上却被报了'); bad += 1
    # 坏例17i：CI 块里删掉一行，文档那句「N 项离线检查」必须当场过期
    if count_ci_block(yml, '离线检查') != 0:
        print('坏例17i：没有那个块却被数出了命令行（算出 %d）' % count_ci_block(yml, '离线检查')); bad += 1
    yml2 = ('      - name: 离线检查\n        run: |\n          python3 tools/a.py\n'
            '          # 注释不许被数成一项检查\n          python3 tools/b.py\n\n'
            '      - name: 下一步\n        run: python3 tools/c.py\n')
    if count_ci_block(yml2, '离线检查') != 2:
        print('坏例17j：离线块实际 2 行命令，却数出 %d（注释/下一块不许算进来）' % count_ci_block(yml2, '离线检查')); bad += 1
    if not doc_number_claims('CI 有 3 项离线检查', {r'(\d+)\s*项离线检查': count_ci_block(yml2, '离线检查')}):
        print('坏例17k：文档写「3 项离线检查」而块里只有 2 行，没被报'); bad += 1
    # 坏例17l：派生计数写进文档后过期，必须当场报（本轮真的发生过：--refresh 之后 apparatus 少了一处）
    ca_pat = {r'按表\s*(\d+)': 35029, r'按裁定表\s*(\d+)': 2074}
    got = doc_number_claims('当场数：按表 35030 处、按裁定表 2075 处', ca_pat)
    if len(got) != 2:
        print('坏例17l：两个过期的派生计数只报了 %d 个：%s' % (len(got), got)); bad += 1
    if doc_number_claims('当场数：按表 35029 处、按裁定表 2074 处', ca_pat):
        print('坏例17m：派生计数对得上却被报了'); bad += 1
    # 坏例17n：出处核对的档位数字过期（本轮真的发生过：一篇从「全对上」挪进「部分对上」）
    t_pat = {r'(\d+)\s*全对上': 214, r'(\d+)\s*部分对上': 37,
             r'(\d+)\s*一句都对不上': 0, r'(\d+)\s*核过没有正文页': 1}
    got2 = doc_number_claims('当场数：215 全对上 / 36 部分对上 / 0 一句都对不上 / 1 核过没有正文页', t_pat)
    if len(got2) != 2:
        print('坏例17n：过期的是两个档位数字，却只报了 %d 个：%s' % (len(got2), got2)); bad += 1
    if doc_number_claims('当场数：214 全对上 / 37 部分对上 / 0 一句都对不上 / 1 核过没有正文页', t_pat):
        print('坏例17o：出处核对数字对得上却被报了'); bad += 1

    if bad:

        print('[!] audit-content --selftest 失败 %d 项' % bad)

        return 1

    import ast, inspect
    # 坏例子个数当场从这份源码数出来（数 `bad += 1` 这个语句本身）。
    # 先前数的是源码文本里 'bad += 1' 出现几次——把计数那一行自己也数了进去，多报一个。
    _n = sum(1 for _x in ast.walk(ast.parse(inspect.getsource(selftest)))
             if isinstance(_x, ast.AugAssign) and isinstance(_x.value, ast.Constant) and _x.value.value == 1)
    print('[ok] audit-content --selftest 通（%d 个坏例子全部试到）' % _n)

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
    aj = ROOT / 'docs' / 'accuracy.md'
    accuracy_md = aj.read_text(encoding='utf-8') if aj.exists() else ''
    vy = ROOT / '.github' / 'workflows' / 'verify.yml'
    verify_yml = vy.read_text(encoding='utf-8') if vy.exists() else ''
    res = audit(corpus, ledger, tsrc, defects, trad, trad_md, accuracy_md, verify_yml)

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

              '- 出处核对：' + ' / '.join('%s %d' % (k.split('·', 1)[1], g[k])
                                          for k in sorted(k for k in g if k.startswith('出处核对·'))),

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

