# -*- coding: utf-8 -*-
"""异体字等价表：出处核对里大量「差一句」其实是同一个字的两种写法
   （未尝/未甞、概/槩、青/靑、卫/衞、厄/戹、告/吿）。
   不认这些字，工具就把「页里写作另一个写法」报成「我们对不上」——那是工具的脆，不是内容的错。

   数据源：Unicode Unihan 官方异体字段（data/unihan/Unihan_Variants.txt，Unicode 许可）。
   口径：这张表**只用于比对**，绝不用来改写仓内正文；正文用哪个字由教材与第二条来源决定。
"""
import json, re, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = ROOT / 'data' / 'unihan' / 'Unihan_Variants.txt'
ZIP = ROOT / 'data' / 'unihan' / 'Unihan.zip'
OUT = ROOT / 'data' / 'char-variants.json'
POEMS = ROOT / 'data' / 'poems.json'

# 参与合并的字段。kSemanticVariant 故意排除：它连的是「义近字」（說/悅、知/智），
# 那种字在古文里常常就是不同的词，当成异体去比对会把真差异抹平。
USE_FIELDS = ('kSimplifiedVariant', 'kTraditionalVariant', 'kEquivalentVariant',
              'kCompatibilityVariant', 'kSpecializedVariant')
EXCLUDED = ('kSemanticVariant', 'kTotalMatchedComponent')

CP = re.compile(r'U\+([0-9A-Fa-f]{4,6})')


def chars(cell):
    out = []
    for m in CP.finditer(cell or ''):
        try:
            out.append(chr(int(m.group(1), 16)))
        except Exception:
            pass
    return out


def ensure_variants():
    if VARIANTS.exists():
        return
    print('先取 Unihan_Variants.txt…')
    if not ZIP.exists():
        import urllib.request
        url = 'https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip'
        req = urllib.request.Request(url, headers={'User-Agent': 'diuci-content/1.0 (hi@diuci.com)'})
        with urllib.request.urlopen(req, timeout=90) as r, ZIP.open('wb') as f:
            f.write(r.read())
    with zipfile.ZipFile(str(ZIP)) as z:
        z.extract('Unihan_Variants.txt', str(ROOT / 'data' / 'unihan'))


def build():
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    provenance = {}
    total = 0
    with VARIANTS.open(encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 3 or parts[1] not in USE_FIELDS:
                continue
            a = chr(int(parts[0][2:], 16))
            for b in chars(parts[2]):
                union(a, b)
                total += 1
                provenance.setdefault((min(a, b), max(a, b)), set()).add(parts[1])

    groups = {}
    for ch in list(parent):
        groups.setdefault(find(ch), set()).add(ch)

    # 只保留仓内正文真的用到的字所在的组：表小、可审计，不会把无关字混进来。
    used = set()
    pj = json.loads(POEMS.read_text(encoding='utf-8'))
    for p in pj['poems']:
        for key in ('lines', 'linesPunct', 'fullLines', 'fullLinesPunct'):
            for x in (p.get(key) or []):
                used.update(x)

    keep, dropped = {}, 0
    for root, members in groups.items():
        if len(members) < 2:
            continue
        hit = [c for c in members if c in used]
        if not hit:
            dropped += 1
            continue
        rep = min(members)
        for c in members:
            keep[c] = rep
    fields = {}
    for (a, b), fs in provenance.items():
        fields[a + b] = sorted(fs)

    out = {
        'note': '异体字等价表。只用于「出处核对」的比对，不用于改写仓内正文：'
                '正文用哪个字由教材版与第二条独立来源决定。',
        'source': 'Unicode Unihan（data/unihan/Unihan_Variants.txt，Unicode 许可）',
        'fields_used': list(USE_FIELDS),
        'fields_excluded': list(EXCLUDED),
        'excluded_reason': 'kSemanticVariant 连的是义近字（說/悅、知/智），在古文里常常是不同的词，'
                           '当成异体会把真差异抹平；kTotalMatchedComponent 是构件相同，不是同字。',
        'pairs': total,
        'groups_kept': sum(1 for v in groups.values() if len(v) > 1),
        'groups_dropped_unused': dropped,
        'map': keep,
        'fields_of': fields,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print('[异体字表] 合并 %d 对 / 保留组 %d 个（仓内用字相关的组）/ 丢弃与仓内无关的组 %d 个 / 映射字 %d 个'
          % (total, out['groups_kept'], dropped, len(keep)))
    return out


def selftest():
    d = build()
    m = d['map']
    # 坏例1：未尝/未甞 不同组，赤壁赋那句就永远「对不上」
    assert m.get('甞') == m.get('嘗') or m.get('甞') == m.get('尝'), '坏例1：甞 没并进 嘗/尝 组'
    # 坏例2：槩/概 不同组（黄冈竹楼记）
    assert m.get('槩') == m.get('概'), '坏例2：槩 没并进 概 组'
    # 坏例3：靑/青、衞/卫、戹/厄、吿/告 必须同组
    for a, b in (('靑', '青'), ('衞', '卫'), ('戹', '厄'), ('吿', '告'), ('顚', '颠')):
        assert m.get(a) == m.get(b), '坏例3：%s/%s 没并成一组' % (a, b)
    # 坏例4：义近字不许当异体
    assert m.get('說') != m.get('悅') and m.get('知') != m.get('智'), '坏例4：义近字被当成异体字'
    # 坏例5：每组必须留下来源字段，不能只给一个合并结果（不可审计）
    assert d['fields_of'], '坏例5：合并结果没有留下来源字段'
    # 坏例6：代表字必须是真实汉字，不许出现把「願」映射成生僻字那种事
    for k, v in m.items():
        assert ord(v) >= 0x3000, '坏例6：%s 被映射到可疑字符 %s' % (k, v)
    print('[ok] build-char-variants --selftest 通（6 个坏例子全部试到）')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ensure_variants()
    if '--selftest' in sys.argv:
        selftest()
    else:
        build()
