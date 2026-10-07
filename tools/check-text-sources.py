#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正文出处交叉核对：仓内每一篇的原文，能不能在独立来源里找到。

为什么必须有这一步：仓里出现过**编造的正文**——《虽有嘉肴》的「是故无冥明之察」
「善哉，答是」四句根本不是《礼记》原文，注释译文赏析还围着它编了一整套。
现有校验器查不出这种东西：它查格式、查字数、查版权，不查「这段话是不是真的」。

做法：
  1. 用维基文库（zh.wikisource.org）的检索接口找篇目页；
  2. 取页面正文，繁体转简体（OpenCC TSCharacters 字表，Apache-2.0）；
  3. 把仓内每一句（剥标点）拿去页面里找；
  4. 结果写 data/text-sources.json：每篇记「找到了哪一页、几句对上、几句没对上」。

这一步不替你改正文，它只把「对不上」的篇目摊出来。
用法：
  python tools/check-text-sources.py            # 全仓
  python tools/check-text-sources.py --limit 12 # 先试一小批
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import match as M  # noqa: E402
import validate as V  # noqa: E402

API = 'https://zh.wikisource.org/w/api.php'
UA = {'User-Agent': 'diuci-content-check/1.0 (contact: hi@diuci.com)'}
OUT = ROOT / 'data' / 'text-sources.json'
T2S = ROOT / 'data' / 'opencc' / 'TSCharacters.txt'


def http_json(params):
    url = API + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def load_t2s():
    """繁体 → 简体 单字表。只用来比对，不用来改写仓内正文。"""
    if not T2S.exists():
        raise SystemExit('缺 %s：先下载 OpenCC 的 TSCharacters.txt（Apache-2.0）' % T2S)
    table = {}
    for line in T2S.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            table[parts[0]] = parts[1]
    return table


def to_simplified(text, table):
    return ''.join(table.get(ch, ch) for ch in text)


def page_text(title):
    d = http_json({'action': 'parse', 'page': title, 'prop': 'text', 'format': 'json'})
    html = d.get('parse', {}).get('text', {}).get('*', '')
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<sup[^>]*class="[^"]*Reference[^"]*"[^>]*>.*?</sup>', '', html, flags=re.S)
    txt = re.sub(r'<[^>]+>', '', html)
    txt = re.sub(r'&[a-z]+;', ' ', txt)
    return txt


def search_page(query):
    d = http_json({'action': 'query', 'list': 'search', 'srsearch': query,
                   'srlimit': 5, 'format': 'json'})
    return [x['title'] for x in d.get('query', {}).get('search', [])]


def clean(text, table):
    text = to_simplified(text, table)
    for ch in M.PUNCT + '\u3000\xa0':
        text = text.replace(ch, '')
    return re.sub(r'\s', '', text)


def main():
    limit = 0
    for i, a in enumerate(sys.argv):
        if a == '--limit':
            limit = int(sys.argv[i + 1])

    if not T2S.exists():
        print('先取 OpenCC 字表（Apache-2.0）…')
        urls = ['https://cdn.jsdelivr.net/gh/BYVoid/OpenCC@master/data/dictionary/TSCharacters.txt',
                'https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TSCharacters.txt']
        blob = None
        last = None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=60) as r:
                    blob = r.read().decode('utf-8', 'replace')
                break
            except Exception as exc:
                last = exc
        if blob is None:
            raise SystemExit('取不到 OpenCC 字表：%s' % last)
        T2S.parent.mkdir(parents=True, exist_ok=True)
        T2S.write_text(blob, encoding='utf-8')
        print('  已存 %s（%d 字节）' % (T2S, len(blob)))

    table = load_t2s()
    poems = V.load_poems()
    if limit:
        poems = poems[:limit]

    results = []
    stats = {'attested': 0, 'partial': 0, 'notfound': 0, 'nosource': 0}
    for n, p in enumerate(poems, 1):
        title = p['title']
        author = p.get('author') or ''
        lines = [M.strip_punct(x) for x in (p.get('lines') or [])]
        lines = [x for x in lines if x]
        query = '%s %s' % (title, '' if author in ('佚名', '乐府', '民歌') else author)
        rec = {'id': p['id'], 'title': title, 'author': author,
               'query': query.strip(), 'page': None, 'url': None,
               'lines': len(lines), 'hit': 0, 'miss': []}
        try:
            cands = search_page(rec['query'])
            t2s_cands = [to_simplified(c, table) for c in cands]
            page = None
            for raw, conv in zip(cands, t2s_cands):
                base = M.norm_base(title)
                if base and base in conv:
                    page = raw
                    break
            if page is None and cands:
                page = cands[0]
            if page:
                rec['page'] = page
                rec['url'] = 'https://zh.wikisource.org/wiki/' + urllib.parse.quote(page)
                src_txt = clean(page_text(page), table)
                for idx, ln in enumerate(lines):
                    if ln and ln in src_txt:
                        rec['hit'] += 1
                    else:
                        rec['miss'].append(ln)
                if rec['hit'] == rec['lines']:
                    stats['attested'] += 1
                elif rec['hit']:
                    stats['partial'] += 1
                else:
                    stats['notfound'] += 1
            else:
                stats['nosource'] += 1
        except Exception as exc:
            rec['error'] = '%s: %s' % (type(exc).__name__, exc)
            stats['nosource'] += 1
        results.append(rec)
        flag = 'ok' if rec['hit'] == rec['lines'] and rec['lines'] else '!!'
        print('[%3d/%3d] %s %s（%s）  %d/%d 句对上  %s' % (
            n, len(poems), flag, title, author, rec['hit'], rec['lines'],
            rec['page'] or '找不到页面'))
        time.sleep(0.12)

    OUT.write_text(json.dumps({
        'note': '每篇原文的独立出处核对结果。来源：维基文库 zh.wikisource.org（公有领域文本）。'
                '繁体转简体用 OpenCC TSCharacters 字表（Apache-2.0），只用于比对，不改仓内正文。',
        'generated': time.strftime('%Y-%m-%d'),
        'stats': stats,
        'results': results,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    print()
    print('出处核对：%d 全对上 / %d 部分对上 / %d 一句都对不上 / %d 找不到来源页'
          % (stats['attested'], stats['partial'], stats['notfound'], stats['nosource']))
    print('已写 data/text-sources.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
