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
# 一条合格的异文必须断言「这里有另一种写法」。不这么断言的条目不是异文，
# 是版权说明、待办登记、通假字解释——以前也被算进「异文条目总数」，把分母撑虚。
VARIANT_MARK = re.compile(r'一作|别本|他本|另一本|版本作|来源页作|夹注|异体|旧本作|通行本作|误作')
BOOK_RE = re.compile(r'《[^》]{2,24}》')
OTHER_BOOK_RE = re.compile(r'《[^》]{2,20}》')
PICK_RE = re.compile(r'取舍|本仓从|从「')


def enrich(t, page, url, volume=''):
    """返回 (新文本, 补了几条出处, 补了几条取舍)。只动 ## 异文 小节。"""
    m = re.search(r'^## 异文[^\n]*\n(.*?)(?=^## |\Z)', t, re.M | re.S)
    if not m:
        return t, 0, 0
    body = m.group(1)
    added = 0
    out_lines = []
    for ln in body.split('\n'):
        s = ln.rstrip()
        if s.strip().startswith('- ') and '出处' not in s:
            if CITE_RE.search(s) and URL_RE.search(page) is None and url:
                s = s.rstrip('。') + '。出处：维基文库《%s》 %s' % (page, url)
                added += 1
            elif BOOK_RE.search(s):
                # 条目自己点了某本书的名，出处就是那本书——照它写的记，不换成别的来源。
                book = BOOK_RE.search(s).group(0)
                s = s.rstrip('。') + '。出处：仓内所记版本 %s（按条目原引，未另附链接）' % book
                added += 1
            elif '教材' in s and volume:
                # 取舍理由是「与教材一致」的，出处写教材哪一册——只许写册次，不许编课号。
                s = s.rstrip('。') + '。出处：统编教材《语文》%s（frontmatter 记录的册次）' % volume
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
        mv = re.search(r'^volume:\s*(.+)$', t, re.M)
        new_t, a, _ = enrich(t, page, rec['url'], (mv.group(1).strip() if mv else ''))
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
    # 3) 引的是别的书：出处只能记那本书，不许安到维基文库头上
    book = '## 异文\n- 「又恐琼楼玉宇」：《白香词谱笺》作「惟恐琼楼玉宇」。\n'
    t3, a3, _ = enrich(book, page, url, '九年级上册')
    assert a3 == 1 and '白香词谱笺' in t3 and url not in t3, '坏例3：把别的书的话安到维基文库头上'
    # 4) 不该补的：整条跟来源页无关
    plain = '## 异文\n- 「长久」：通行本作「长久」，别本作「长健」。\n'
    t4, a4, _ = enrich(plain, page, url)
    assert a4 == 0, '坏例4：没说是哪一页的，也补了 URL'
    # 5) 小节边界：不能把下一个小节吞进去
    two = '## 异文\n- 「甲」：来源页作「乙」。\n\n## 收录范围\n- 只收前四句。\n'
    t5, a5, _ = enrich(two, page, url)
    assert '## 收录范围' in t5 and t5.count(url) == 1, '坏例5：越界改了别的小节'
    # 6) 引书名的条目：出处记那本书，不冒充维基文库
    b6 = '## 异文\n- 「但愿人长久」：《白香词谱笺》作「惟恐琼楼玉宇」，本仓从通行本。\n'
    t6, a6, _ = enrich(b6, page, url, '九年级上册')
    assert a6 == 1 and '白香词谱笺' in t6 and url not in t6, '坏例6：把书名换成维基文库的页'
    # 7) 讲教材的条目：出处写册次，不编课号
    b7 = '## 异文\n- 「甲」：来源页夹注「于／於」。取舍：从「于」，与教材一致。\n'
    t7, a7, _ = enrich(b7, '', '', '九年级上册')
    assert a7 == 1 and '九年级上册' in t7, '坏例7：没写册次'
    # 8) 没有册次依据的不能写教材出处
    b8 = '## 异文\n- 「甲」：与教材一致。\n'
    t8, a8, _ = enrich(b8, '', '', '')
    assert a8 == 0, '坏例8：没有册次依据也写了教材出处'
    # 9) 已经有出处的不重复补
    b9 = '## 异文\n- 「甲」：《乙》作「丙」。出处：仓内所记版本《乙》。\n'
    t9, a9, _ = enrich(b9, page, url, '九年级上册')
    assert a9 == 0, '坏例9：重复补出处'
    print('[ok] enrich-variants --selftest 通（9 个坏例子全部被拦住）')


if SELFTEST:
    selftest()
else:
    main()
