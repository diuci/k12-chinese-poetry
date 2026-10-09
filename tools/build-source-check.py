# -*- coding: utf-8 -*-
"""把「没全对上的那几句」逐句摊开：我们怎么写的、来源页怎么写的、差在哪。
   出处核对报「部分对上」只是一个数字；这一页才是考证本身。

   三档口径，不许含糊：
     A 只差写法   —— 页里明写着这一句，用的全是同一个字的另一种写法（异体）。
     B 页里写作…  —— 页里有这一句，但多字、少字、或夹着异文（版本差异）。
     C 页里没找到 —— 找不到够像的一段；可能是页选错、版本不同，或我们这边有问题。
"""
import importlib.util, json, sys, difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TSRC = ROOT / 'data' / 'text-sources.json'
OUT = ROOT / 'docs' / 'source-check.md'
JOUT = ROOT / 'data' / 'source-check.json'
BT = chr(96)


def loader():
    spec = importlib.util.spec_from_file_location('cts_srccheck', ROOT / 'tools' / 'check-text-sources.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def best_window(ours, txt):
    """锚在句首字上找最像的一段：四库全书那种十几万字的页，逐位扫跑不完。

    锚点必须是第一个真正的字：仓里有些正文以 ASCII 引号开头（"传其事以为官戒也），
    拿引号当锚点，页里那个字符当然找不到——窗口是空的，这一句就被写成「页里没找到」，
    而页里明写着那一句（只差一个「也」字）。种树郭橐驼传 就是这么掉进 C 的。"""
    best, br = None, -1.0
    anchor = ''
    for ch in ours:
        if ch.isalnum() or '\u4e00' <= ch <= '\u9fff':
            anchor = ch
            break
    if not anchor or not txt:
        return None, 0.0
    i = txt.find(anchor)
    while i >= 0:
        w = txt[i:i + len(ours) + 6]
        s = difflib.SequenceMatcher(None, ours, w).ratio()
        if s > br:
            br, best = s, w
        i = txt.find(ours[0], i + 1)
    return best, br


def classify(ours, page_line):
    """返回 (档位 A/B/C, 差异说明)。"""
    if not page_line:
        return 'C', '页里找不到够像的一段'
    sm = difflib.SequenceMatcher(None, ours, page_line)
    d, glyph_only = [], True
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        A, B = ours[a1:a2], page_line[b1:b2]
        d.append((tag, A, B))
        if not (tag == 'replace' and len(A) == 1 and len(B) == 1):
            glyph_only = False
    if not d:
        return 'A', '页里与我们写法相同（这一句其实对上了，是核对方法没认出来）'
    if glyph_only:
        bits = '、'.join('页里作「%s」我们作「%s」' % (b, a) for _, a, b in d)
        return 'A', '只差一个字的写法：' + bits
    bits = []
    for tag, a, b in d:
        if tag == 'replace':
            bits.append('页里「%s」我们「%s」' % (b, a))
        elif tag == 'insert':
            bits.append('页里多「%s」' % b)
        else:
            bits.append('页里少「%s」' % a)
    return 'B', '；'.join(bits[:6])


def build():
    d = json.loads(TSRC.read_text(encoding='utf-8'))
    rows = [r for r in d['results'] if r.get('page') and r['hit'] < r['lines']]
    rows.sort(key=lambda r: (-(r['lines'] - r['hit']), r['title']))
    m = loader()
    table = m.load_t2s()
    counts = {'A': 0, 'B': 0, 'C': 0}
    L = ['# 出处核对：没全对上的那几句，逐句写明差在哪', '',
         '> 这一页由 tools/build-source-check.py 生成，不要手改。',
         '> 数据来自 data/text-sources.json（核对日期 %s）。' % d.get('generated'),
         '',
         '核对单位是**句子**：把仓里每一句剥掉标点，拿去来源页里逐句找。',
         '没对上的句子分三档，不含糊：',
         '',
         '- **A 只差写法**：页里明写着这一句，用的是同一个字的另一种写法（异体字）。',
         '- **B 页里写作…**：页里有这一句，但多字、少字，或夹着异文——这是版本差异。',
         '- **C 页里没找到**：找不到够像的一段。可能是页选错、版本不同，也可能我们这边有问题。',
         '',
         '共 %d 篇没全对上，涉及 %d 句。' % (len(rows), sum(r['lines'] - r['hit'] for r in rows)),
         '']
    detail = []
    for r in rows:
        txts = []
        for pg in r['page'].split(' + '):
            try:
                _, t = m.page_text(pg)
                txts.append(m.clean(t, table)[0])
            except Exception:
                pass
        txt = ''.join(txts)
        L.append('## %s（%s）  %d/%d 句对上' % (r['title'], r.get('author') or '佚名', r['hit'], r['lines']))
        L.append('')
        L.append('- 来源页：%s' % r['page'])
        items = []
        for mm in (r.get('miss') or []):
            ours = mm['line']
            # 核对那一步已经算过「页里最像的一段」（check-text-sources.nearest）。
            # 这里再算一遍就是第二份口径——两份口径迟早给出两个答案，
            # 而写进文档的是后一份。现成的先用，没有才自己找。
            near = mm.get('nearest') or None
            if near:
                w, ratio = near['source'], near['ratio']
            else:
                w, ratio = best_window(ours, txt)
            grade, note = classify(ours, w if ratio >= 0.55 else None)
            counts[grade] += 1
            L.append('- 没对上：' + BT + ours + BT)
            L.append('  - **%s** %s' % (grade, note))
            if grade != 'A' and w:
                L.append('  - 页里这一段：%s' + BT)
                L[-1] = '  - 页里这一段：' + BT + w[:56] + BT + '（相似度 %.2f）' % ratio
            items.append({'line': ours, 'grade': grade, 'note': note,
                          'window': (w or '')[:56], 'ratio': round(ratio, 2)})
        detail.append({'id': r['id'], 'title': r['title'], 'hit': r['hit'], 'lines': r['lines'],
                       'page': r['page'], 'items': items})
        L.append('')
    L.append('## 小结')
    L.append('')
    L.append('- A 只差写法（异体字）：%d 句' % counts['A'])
    L.append('- B 页里写作别的样子（版本差异）：%d 句' % counts['B'])
    L.append('- C 页里没找到：%d 句' % counts['C'])
    L.append('')
    L.append('A 不等于「我们写错了」：仓里的用字以统编教材为准，古籍写作另一个字形是同一个字。')
    L.append('B 不等于「我们写错了」：那是版本差异，我们照实列出来，让读者自己看得见。')
    L.append('C 必须让读者看得见：背诵与默写以教材和老师的要求为准。')
    L.append('')
    OUT.write_text('\n'.join(L), encoding='utf-8')
    # 同一份考证，两种用法：docs/source-check.md 给人读，data/source-check.json 给站点逐篇渲染。
    # 站点不许自己另数一遍、另判一遍——它只搬这一份。
    JOUT.write_text(json.dumps({'generated': d.get('generated'), 'note':
                                '逐句核对明细。grade：A 只差写法 / B 页里写作别的样子 / C 页里没找到。',
                                'rows': detail}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('[出处核对明细] %d 篇 / %d 句：A %d、B %d、C %d → docs/source-check.md 与 data/source-check.json'
          % (len(rows), sum(counts.values()), counts['A'], counts['B'], counts['C']))
    return rows, counts


def selftest():
    # 坏例1：只差写法必须被认成 A（未尝/未甞）
    g1, n1 = classify('逝者如斯而未尝往也', '逝者如斯而未甞往也')
    assert g1 == 'A' and '甞' in n1, '坏例1：只差写法没被认出来'
    # 坏例2：多一个字的版本差异不许被说成只差写法
    g2, _ = classify('然概乎其中', '槩乎其中')
    assert g2 == 'B', '坏例2：多一个字被当成同一个字的写法'
    # 坏例3：页里根本没有这句，必须落到 C，不许含糊成 A/B
    g3, _ = classify('此四君者皆明智而忠信', None)
    assert g3 == 'C', '坏例3：页里没有的句子被归到了 A/B'
    # 坏例4：相似度太低的窗口不许当「页里有这句」
    g4, _ = classify('茅屋为秋风所破歌安得广厦千万间', '贾谊过秦论云诸侯不测')
    assert g4 == 'B' or g4 == 'C', '坏例4：毫不相干的窗口被当成 A'
    # 坏例5：明细必须覆盖所有没全对上的篇与句，一篇一句都不能漏
    rows, counts = build()
    src = json.loads(TSRC.read_text(encoding='utf-8'))
    want_rows = [r for r in src['results'] if r.get('page') and r['hit'] < r['lines']]
    assert len(rows) == len(want_rows), '坏例5：明细漏了篇（%d / %d）' % (len(rows), len(want_rows))
    want_lines = sum(r['lines'] - r['hit'] for r in want_rows)
    assert sum(counts.values()) == want_lines, '坏例5b：句数对不上（%d / %d）' % (sum(counts.values()), want_lines)
    # 坏例6：每一句都必须落到某一档，不许出现「没分类」的句子
    txt = OUT.read_text(encoding='utf-8')
    assert txt.count('- **A**') + txt.count('- **B**') + txt.count('- **C**') == want_lines, '坏例6：有句子没落到档'
    # 坏例7：以引号开头的句子，锚点不许是那个引号——页里没有引号字符，窗口就是空的，
    # 这一句会被写成「页里没找到」，而页里明写着它（只差一个「也」字）。
    _t7 = ('吾问养树得养人术传其事以为官戒此唐朝作品在全世界都属于公有领域因为作者逝世已经超过100年')
    _w7, _r7 = best_window('"传其事以为官戒也', _t7)
    assert _w7 and _r7 >= 0.55, '坏例7：引号当锚点，页里明写着的那一段没找出来（窗口=%r）' % _w7
    assert classify('"传其事以为官戒也', _w7)[0] == 'B', '坏例7b：页里少一个「也」字没被判成版本差异'
    # 坏例8：核对那一步算好的「页里最像的一段」必须被用上——自己再算一遍就是第二份口径
    _near = {'source': '人复起必从吾言矣宰我子贡善为说辞冉牛闵子颜渊善言德行孔子兼之曰我', 'ratio': 0.667}
    _g8 = classify('"公孙丑曰"宰我子贡善为说辞冉牛闵子颜渊善言德行', _near['source'])[0]
    assert _g8 == 'B', '坏例8：页里有这一段（我们多一个主语）却没落到 B（判成 %s）' % _g8
    # 坏例9：真没有的句子必须落到 C，不许因为窗口找松了就含糊
    assert best_window('此四君者皆明智而忠信', _t7)[1] < 0.55, '坏例9：毫不相干的窗口被当成页里有这句'
    print('[ok] build-source-check --selftest 通（9 个坏例子全部试到）')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if '--selftest' in sys.argv:
        selftest()
    else:
        build()
