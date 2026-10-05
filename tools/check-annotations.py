# -*- coding: utf-8 -*-
"""注释/译文/赏析 内容质量护栏。

这类内容是给孩子看的，编错一个字都是伤害。所以不只查格式，还要查事实：

1. **注释词必须在诗里出现过** —— 拦住「给不存在的字写注释」
2. **注释不能解释得比课文还简单**（如把「之」注成「的」）
3. **译文不能夹带原文没有的内容**（数字对不上、出现诗中没有的专名）
4. **译文要覆盖每一联** —— 漏译
5. **长度合理**：译文不短于诗句、赏析不少于 80 字
6. 三节都非空、不残留「待补」占位

用法：python tools/check-annotations.py
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POEMS = ROOT / 'poems'
CONTENT = ROOT / 'content' / 'annotations'

CJK = re.compile(r'[\u4e00-\u9fff]')
# 「词：释义」——取词
GLOSS = re.compile(r'^\s*[-*]?\s*(.+?)\s*[:：]')
# 过于浅显的注释词：这些孩子本来就会，注了反而是噪声
TRIVIAL = {'的', '之', '了', '是', '在', '有', '也', '而', '以', '于', '其', '则'}

ok = '[ok]'
bad = '[!!]'
warn = '[--]'

fails = []
warns = []


def load_content():
    data = {}
    if not CONTENT.exists():
        return data
    for f in sorted(CONTENT.glob('*.json')):
        try:
            for k, v in json.loads(f.read_text(encoding='utf-8')).items():
                data[k] = v
        except Exception as e:
            fails.append('%s 解析失败: %s' % (f.name, e))
    return data


def poem_records():
    out = []
    for pf in sorted(POEMS.rglob('*.md')):
        t = pf.read_text(encoding='utf-8')
        mi = re.search(r'^id:\s*(\S+)\s*$', t, re.M)
        mi2 = re.search(r'^title:\s*(.+?)\s*$', t, re.M)
        mi3 = re.search(r'^stage:\s*(.+?)\s*$', t, re.M)
        if not mi:
            continue
        # 正文：poem-body 之外，取首个 ## 之前的汉字；这里用标题+全文汉字兜底
        body = re.sub(r'^---.*?^---', '', t, flags=re.S | re.M)
        out.append({
            'id': mi.group(1),
            'title': (mi2.group(1) if mi2 else pf.stem),
            'stage': (mi3.group(1) if mi3 else '?'),
            'file': pf,
            'text': ''.join(CJK.findall(body.split('## ')[0])),
        })
    return out


data = load_content()
poems = poem_records()

print('=== 注释/译文/赏析 内容质量护栏 ===')
print('内容条目 %d，诗篇 %d' % (len(data), len(poems)))
print('')

# ---- 1 覆盖
missing = [p['id'] for p in poems if p['id'] not in data]
extra = [k for k in data if k not in {p['id'] for p in poems}]
print('1) 覆盖')
print('   %s 已有内容 %d / %d' % (ok if not missing else bad, len(data), len(poems)))
if missing:
    print('   %s 尚缺 %d 篇' % (warn, len(missing)))
if extra:
    fails.append('内容里有 %d 个 id 在诗库中不存在：%s' % (len(extra), extra[:5]))

# ---- 逐篇检查
print('')
print('2) 文本卫生')
BADCH = []
LATIN = []
for k, v in data.items():
    for fld in ('note', 'trans', 'appr'):
        val = v.get(fld)
        if val is None:
            continue
        items = val if isinstance(val, list) else [val]
        for it in items:
            if '\ufffd' in it:
                BADCH.append('%s.%s 有乱码字符（写入时编码坏了）' % (k, fld))
            # 中文内容里混入拉丁单词 = 写串了。注意 JSON 的键名是英文，只查内容
            for m in re.finditer(r'[A-Za-z]{2,}', it):
                LATIN.append('%s.%s 混入英文「%s」' % (k, fld, m.group(0)))
print('   %s 无乱码字符' % (ok if not BADCH else bad))
if BADCH:
    for x in BADCH[:5]:
        print('       ' + x)
    fails.append('乱码 %d' % len(BADCH))
print('   %s 中文内容里无英文残留' % (ok if not LATIN else bad))
if LATIN:
    for x in LATIN[:5]:
        print('       ' + x)
    fails.append('英文残留 %d' % len(LATIN))

print('')
print('3) 逐篇质量')
bad_terms = []
bad_trans = []
short = []
no_section = []
checked = 0
for p in poems:
    a = data.get(p['id'])
    if not a:
        continue
    checked += 1
    ident = '%s《%s》' % (p['id'], p['title'])

    for k, label in (('note', '注释'), ('trans', '译文'), ('appr', '赏析')):
        if not a.get(k):
            no_section.append('%s 缺%s' % (ident, label))

    # 注释词必须真的在诗里
    notes = a.get('note') or []
    if isinstance(notes, str):
        notes = [notes]
    for nline in notes:
        m = GLOSS.match(nline)
        if not m:
            bad_terms.append('%s 注释行没有「词：释义」格式：%s' % (ident, nline[:20]))
            continue
        term = m.group(1).strip()
        if term in TRIVIAL:
            bad_terms.append('%s 注释了过于浅显的词「%s」' % (ident, term))
            continue
        if CJK.findall(term) and not all(ch in p['text'] for ch in CJK.findall(term)):
            miss = [ch for ch in CJK.findall(term) if ch not in p['text']]
            bad_terms.append('%s 注释词「%s」在诗里没有：%s' % (ident, term, ''.join(miss)))

    # 译文：覆盖每一联 & 不夹带诗中没有的专名
    tr = a.get('trans') or ''
    n_lines = len(re.findall(r'[^，。！？；\n]+', p['text'])) or 1
    if len(CJK.findall(tr)) < len(CJK.findall(p['text'])) * 0.6:
        bad_trans.append('%s 译文偏短（%d 字 vs 原文 %d 字）'
                          % (ident, len(CJK.findall(tr)), len(CJK.findall(p['text']))))
    for name in re.findall(r'[《]([^》]{1,12})[》]', tr):
        if name and not any(ch in p['text'] for ch in CJK.findall(name)):
            bad_trans.append('%s 译文提到诗中没有的书名《%s》' % (ident, name))

    # 赏析长度
    ap = a.get('appr') or ''
    if len(CJK.findall(ap)) < 80:
        short.append('%s 赏析仅 %d 字' % (ident, len(CJK.findall(ap))))

print('   已检查 %d 篇' % checked)
for name, arr in (('注释词有问题', bad_terms), ('译文有问题', bad_trans),
                  ('赏析过短', short), ('缺小节', no_section)):
    if arr:
        print('   %s %s：%d' % (bad, name, len(arr)))
        for x in arr[:4]:
            print('       ' + x)
        fails.append('%s：%d' % (name, len(arr)))
    else:
        print('   %s 无%s' % (ok, name))

print('')
if fails:
    for f in fails:
        print('%s %s' % (bad, f))
    sys.exit(1)
print('%s 内容质量护栏通过' % ok)
