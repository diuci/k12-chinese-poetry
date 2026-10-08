#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「仓内没核到」的异文找新来源页——直接拿别本写法去维基文库全文搜。

《吕氏春秋》「维基文库没有可用页面」的结论是错的：按篇名找页名全是空页，
拿正文句子去搜才找到 呂氏春秋/卷十四。这一轮把同一招用在整个「没核到」集合上。

但搜到不等于来源。判据只有一条，而且必须是硬的：
  **这一页里装得下这篇的正文**（按句核 ≥ 50%），否则不算来源。
没有这条护栏，「诸子之书」会在《子華子》里被认成《上枢密韩太尉书》的别本，
「茫茫然归」会在《淦隱漫錄》里被认成《孟子》的别本——那是短语撞上了。
"""
import re, sys, importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
_spec = importlib.util.spec_from_file_location('cts', ROOT / 'tools' / 'check-text-sources.py')
C = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(C)
_bls = importlib.util.spec_from_file_location('bl', ROOT / 'tools' / 'build-ledger.py')
bl = importlib.util.module_from_spec(_bls); _bls.loader.exec_module(bl)
VM = bl.VARIANT_MARK
ALT = re.compile(r'(?:本作|一本作|一本无|别本作|来源页作|来源页注|页作|文库作|通行本作|旧本作|他本作|另一本作|误作|》作|一作)\s*「([^」]{2,26})」')
MIN_COVER = 0.5

def np(t):
    return re.sub(r'[\W_]+', '', t or '', flags=re.UNICODE)

def sec_lines(t, name):
    m = re.search(r'^## ' + name + r'\n(.*?)(?=^## |\Z)', t, re.M | re.S)
    if not m:
        return []
    return [x.strip() for x in m.group(1).splitlines() if x.strip() and not x.startswith('>') and not x.startswith('- ')]

def unverified_entries(t):
    m = re.search(r'^## 异文\n(.*?)(?=^## |\Z)', t, re.M | re.S)
    if not m:
        return []
    out, cur = [], None
    for ln in m.group(1).splitlines():
        if ln.startswith('- '):
            if cur: out.append(cur)
            cur = [ln]
        elif cur and ln.strip(): cur.append(ln)
    if cur: out.append(cur)
    return [' '.join(x) for x in out if VM.search(' '.join(x)) and '出处：仓内没核到' in ' '.join(x)]

def units_of(t, table):
    us = []
    for name in ('全文', '必背全文', '必背名句'):
        for ln in sec_lines(t, name):
            for u in re.split(r'(?<=[。！？；])', ln):
                u = u.strip()
                if not u: continue
                k = np(C.clean(u, table)[0])
                if len(k) >= 6: us.append(k)
    return us

def coverage(units, page_np):
    if not units or not page_np:
        return 0.0, 0
    hit = sum(1 for u in units if C.subseq_window(u, page_np, 20))
    return hit / len(units), hit

def selftest():
    table = C.load_t2s()
    # 句单元按「去标点后 ≥6 字」取：短句在整页无标点的散文里没有区分度，本来就不该拿去判覆盖率。
    poem = ('## 全文\n\n'
            '肉食者谋之，又何间焉。\n\n曹刿曰，肉食者鄙。\n\n夫战，勇气也，非一夫之勇。\n\n'
            '## 异文\n- 「又何间焉」：别本作「又何俴焉」。出处：仓内没核到\n')
    us = units_of(poem, table)
    assert len(us) >= 3, '坏例1：本篇的句单元没抽出来'
    # 1) 真来源：整页装得下这篇
    # 页文本在真实流程里是先过繁简转换再 np 的，这里必须照做，否则繁体探针对着简体正文，必然 0 命中。
    same = np(C.clean('肉食者謀之，又何間焉。曹劌曰，肉食者鄙。夫戰，勇氣也，非一夫之勇。小惠未徧。', table)[0])
    f1, h1 = coverage(us, same)
    assert f1 >= MIN_COVER, '坏例2：真来源的覆盖率算低了（%d/%d）' % (h1, len(us))
    # 2) 短语撞上：整页只有这一句撞上
    other = np(C.clean('子華子曰，诸子之书吾未之闻也。', table)[0])
    f2, h2 = coverage(us, other)
    assert f2 < MIN_COVER, '坏例3：短语撞上的被当成来源'
    # 3) 空页不能算来源
    f3, _ = coverage(us, '')
    assert f3 == 0.0, '坏例4：空页被算成有覆盖率'
    # 4) 本篇没有正文节时不许判成 100%（0/0）
    f4, _ = coverage([], same)
    assert f4 == 0.0, '坏例5：没有句单元还算出覆盖率'
    # 5) 只认「仓内没核到」的条目
    assert len(unverified_entries(poem)) == 1, '坏例6：没核到的条目没被挑出来'
    done = poem.replace('出处：仓内没核到', '出处：核到了')
    assert len(unverified_entries(done)) == 0, '坏例7：已经核到的还被挑出来'
    print('[ok] hunt-variant-sources --selftest 通（7 个坏例子全部试到）')
    return 0

def main():
    if '--selftest' in sys.argv:
        return selftest()
    table = C.load_t2s()
    cache = {}
    def page_np(pg):
        if pg not in cache:
            try:
                _, raw = C.page_text(pg)
                tt, _ = C.clean(raw, table)
                cache[pg] = np(tt)
            except Exception:
                cache[pg] = ''
        return cache[pg]
    ok, bad = [], []
    for md in sorted((ROOT / 'poems').rglob('*.md')):
        if md.name == '索引.md':
            continue
        t = md.read_text(encoding='utf-8')
        fid = re.search(r'^id:\s*(\S+)', t, re.M)
        if not fid:
            continue
        us = units_of(t, table)
        if not us:
            continue
        for e in unverified_entries(t):
            hits = ALT.findall(e.replace('*', ''))
            if not hits:
                continue
            claim = hits[-1]
            k = np(C.clean(claim, table)[0])
            if len(k) < 4:
                continue
            try:
                d = C.http_json({'action': 'query', 'list': 'search', 'srsearch': claim, 'srlimit': 6, 'format': 'json'})
            except Exception:
                continue
            for x in d.get('query', {}).get('search', []):
                pg = x['title']
                j = page_np(pg)
                if not j or k not in j:
                    continue
                frac, hit = coverage(us, j)
                rec = (fid.group(1), md.stem, claim, pg, frac, hit, len(us))
                (ok if frac >= MIN_COVER else bad).append(rec)
                break
    print('[找来源] 可以当来源：%d 条；短语撞上、不是这篇书的来源：%d 条' % (len(ok), len(bad)))
    for pid, name, claim, pg, frac, hit, n in ok:
        print('  [可用] %-12s %-20s ← %-40s %d/%d 句' % (name, claim[:20], pg, hit, n))
    for pid, name, claim, pg, frac, hit, n in bad:
        print('  [拒绝] %-12s %-20s ← %-34s 只有 %d/%d' % (name, claim[:20], pg, hit, n))
    return 0

if __name__ == '__main__':
    sys.exit(main())
