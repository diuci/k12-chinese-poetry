# -*- coding: utf-8 -*-
"""给异文条目补出处。

规矩：
- 只给「来源页／维基文库」这一类条目补 URL，URL 取自 data/text-sources.json 里这一篇实际比对过的那一页。
  比对页不是这一页的，不补。
- 引用别的书（《白香词谱笺》《四部丛刊》…）的条目，不补维基文库的 URL——那是另一回事，得单独找来源。
- 不替人做取舍：条目里没写「从哪个」的，不编一个出来。
"""
import json, re, sys, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'text-sources.json'
WRITE = '--write' in sys.argv
SELFTEST = '--selftest' in sys.argv

URL_RE = re.compile(r'https?://')
CITE_RE = re.compile(r'来源页|维基文库|維基文庫')
OTHER_BOOK_RE = re.compile(r'《[^》]{2,20}》')
PICK_RE = re.compile(r'取舍|本仓从|从「')


def enrich(t, page, url):
    """返回 (新文本, 补了几条出处, 补了几条取舍)。只动 ## 异文 小节。"""
    m = re.search(r'^## 异文[^\n]*\n(.*?)(?=^## |\Z)', t, re.M | re.S)
    if not m:
        return t, 0, 0
    body = m.group(1)
    added = 0
    out_lines = []
    for ln in body.split('\n'):
        s = ln.rstrip()
        if s.strip().startswith('- ') and not URL_RE.search(s) and CITE_RE.search(s):
            s = s.rstrip('。') + '。出处：维基文库《%s》 %s' % (page, url)
            added += 1
        out_lines.append(s)
    new_body = '\n'.join(out_lines)
    if not added:
        return t, 0, 0
    return t[:m.start(1)] + new_body + t[m.end(1):], added, 0


def main():
    src = json.loads(SRC.read_text(encoding='utf-8'))
    by_id = {r['id']: r for r in src['results']}
    total = changed = 0
    for md in sorted((ROOT / 'poems').rglob('*.md')):
        if md.name == '索引.md':
            continue
        t = md.read_text(encoding='utf-8')
        fm = re.search(r'^id:\s*(\S+)', t, re.M)
        if not fm:
            continue
        rec = by_id.get(fm.group(1))
        if not rec or not rec.get('page') or not rec.get('url'):
            continue
        page = rec['page'].split(' + ')[0]
        new_t, a, _ = enrich(t, page, rec['url'])
        total += 1
        if a:
            changed += 1
            print('  %-28s 补 %d 条出处 ← %s' % (md.stem, a, page))
            if WRITE:
                md.write_text(new_t, encoding='utf-8')
    print('[异文出处] %d 篇有比对页，其中 %d 篇补了出处' % (total, changed))


def selftest():
    """自带坏例子：不自带坏例子的检查，等于没有检查。"""
    page, url = '测试页', 'https://zh.wikisource.org/wiki/%E6%B5%8B%E8%AF%95%E9%A1%B5'
    # 1) 该补的：提到来源页、没有 URL
    good = '## 异文\n- 「甲光向日金鳞开」：来源页此处夹注「开／𫔭」。取舍：从「开」。\n'
    t, a, _ = enrich(good, page, url)
    assert a == 1 and url in t, '坏例1：该补的没补'
    # 2) 不该补的：已经有 URL
    has = '## 异文\n- 「甲」：来源页作「乙」。出处：维基文库《页》 https://zh.wikisource.org/wiki/x\n'
    t2, a2, _ = enrich(has, page, url)
    assert a2 == 0, '坏例2：已经有 URL 还补一次'
    # 3) 不该补的：引的是别的书
    book = '## 异文\n- 「又恐琼楼玉宇」：《白香词谱笺》作「惟恐琼楼玉宇」。\n'
    t3, a3, _ = enrich(book, page, url)
    assert a3 == 0, '坏例3：把别的书的话安到维基文库头上'
    # 4) 不该补的：整条跟来源页无关
    plain = '## 异文\n- 「长久」：通行本作「长久」，别本作「长健」。\n'
    t4, a4, _ = enrich(plain, page, url)
    assert a4 == 0, '坏例4：没说是哪一页的，也补了 URL'
    # 5) 小节边界：不能把下一个小节吞进去
    two = '## 异文\n- 「甲」：来源页作「乙」。\n\n## 收录范围\n- 只收前四句。\n'
    t5, a5, _ = enrich(two, page, url)
    assert '## 收录范围' in t5 and t5.count(url) == 1, '坏例5：越界改了别的小节'
    print('[ok] enrich-variants --selftest 通（5 个坏例子全部被拦住）')


if SELFTEST:
    selftest()
else:
    main()
