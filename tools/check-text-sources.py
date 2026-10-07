#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正文出处交叉核对：仓内每一篇的原文，能不能在独立来源里找到。

为什么必须有这一步：仓里出现过**编造的正文**——《虽有嘉肴》的「是故无冥明之察」
「善哉，答是」四句根本不是《礼记》原文，注释译文赏析还围着它编了一整套。
现有校验器查格式、查字数、查版权，唯独不查「这段话是不是真的」。

做法：
  1. 维基文库（zh.wikisource.org）检索接口找篇目页；
  2. 挑页：优先标题含篇名、含作者的页；跳过消歧义页、重定向页、
     以及「某某判决书」「某某有限公司」这类同名不同物的页；
  3. 取页面正文，繁体转简体（OpenCC TSCharacters 字表，Apache-2.0）；
  4. 剥掉页面里的「一作某」夹注（顺手记下来，那正是异文线索）；
  5. 把仓内每一句（剥标点）拿去页面里找，记下对上的句数。

这一步不替你改正文，它只把「对不上」的篇目摊出来。
用法：
  python tools/check-text-sources.py            # 全仓
  python tools/check-text-sources.py --limit 12 # 先试一小批
  python tools/check-text-sources.py --stage 高中
"""
import difflib
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

# 同名不同物的页面特征：维基文库也收现代文书，标题撞车的不在少数。
JUNK_HINTS = ('判决书', '纠纷', '有限公司', '通知', '人民政府', '方案', '集团',
              '中学', '大学', '酒店', '医院', '银行', '公司', '学校', '车站',
              '镇', '县', '市', '村', '社区', '协会', '博物馆', '遗址')
# 页面里的夹注：「城春一作荒草木深」——不剥掉就会把真句子判成对不上。
VARIANT_NOTE = re.compile(r'(?:一本作|一作|又作)[\u4e00-\u9fff]{1,4}')
JUNK_NOTE = re.compile(r'作[饭羹品曲者集者]')  # 只登记，不参与判定


def http_json(params):
    url = API + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def load_t2s():
    """繁体 → 简体 单字表。只用来比对，不用来改写仓内正文。"""
    if not T2S.exists():
        raise SystemExit('缺 %s：先跑一次本脚本，它会自动取 OpenCC 字表' % T2S)
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


def ensure_dict():
    if T2S.exists():
        return
    print('先取 OpenCC 字表（Apache-2.0）…')
    urls = ['https://cdn.jsdelivr.net/gh/BYVoid/OpenCC@master/data/dictionary/TSCharacters.txt',
            'https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TSCharacters.txt']
    blob, last = None, None
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


def page_text(title):
    d = http_json({'action': 'parse', 'page': title, 'prop': 'text',
                   'format': 'json', 'redirects': 1})
    parse = d.get('parse') or {}
    html = parse.get('text', {}).get('*', '')
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<sup[^>]*class="[^"]*(?:Reference|noprint)[^"]*"[^>]*>.*?</sup>', '', html, flags=re.S)
    html = re.sub(r'<span[^>]*class="[^"]*(?:mw-editsection|noprint)[^"]*"[^>]*>.*?</span>', '', html, flags=re.S)
    txt = re.sub(r'<[^>]+>', ' ', html)
    txt = re.sub(r'&[a-z]+;', ' ', txt)
    return parse.get('title', title), txt


def search_pages(query):
    d = http_json({'action': 'query', 'list': 'search', 'srsearch': query,
                   'srlimit': 6, 'format': 'json'})
    return [x['title'] for x in d.get('query', {}).get('search', [])]


def clean(text, table):
    """繁→简、剥标点空白。返回 (清洗后文本, 夹注列表)。

    夹注（「城春一作荒草木深」）只登记、不剥掉：剥掉会把句子切碎，
    反而让真句子判成对不上。打断交给 line_in 的 annotated / near 两档去认。"""
    text = to_simplified(text, table)
    notes = VARIANT_NOTE.findall(text)
    for ch in M.PUNCT + '\u3000\xa0↑↓*#':
        text = text.replace(ch, '')
    return re.sub(r'\s', '', text), notes


def line_in(line, txt):
    """一句在不在来源里。除了整句直接命中，还认「夹注打断」：
    维基文库常把异文夹在正文里（「城春一作荒草木深」），直接找整句会漏。"""
    if line in txt:
        return 'exact'
    if len(line) >= 6:
        head, tail = line[:3], line[-3:]
        i, j = txt.find(head), txt.rfind(tail)
        if i >= 0 and j > i and (j - i) <= len(line) + 16:
            return 'annotated'
    near = nearest(line, txt)
    if near and near['ratio'] >= 0.82:
        return 'near'
    return None


def nearest(line, txt):
    """对不上的句子，找出来源里最接近的一段——这就是异文线索，不是噪声。"""
    L = len(line)
    if not L or len(txt) < 6:
        return None
    best = (0.0, '')
    step = max(1, L // 3)
    span = L + 10
    for i in range(0, max(1, len(txt) - L + 1), step):
        w = txt[i:i + span]
        r = difflib.SequenceMatcher(None, line, w).ratio()
        if r > best[0]:
            best = (r, w)
    if best[0] < 0.55:
        return None
    return {'line': line, 'source': best[1], 'ratio': round(best[0], 3)}


def candidates(title, author, dynasty, table):
    """候选页面排序：标题含篇名 +3，含作者 +2，同名不同物 -8。"""
    base = M.norm_base(title)
    want = M.norm_author(author)
    queries = ['%s %s' % (title, want or '')]
    if want:
        queries.append('%s (%s)' % (title, want))
    if dynasty:
        queries.append('%s %s' % (title, dynasty))
        queries.append('%s (%s)' % (title, dynasty))
    seen, out = set(), []
    for q in queries:
        for c in search_pages(q):
            if c in seen:
                continue
            seen.add(c)
            conv = to_simplified(c, table)
            score = 0
            if base and base in conv:
                score += 3
            if want and want in conv:
                score += 2
            if any(h in conv for h in JUNK_HINTS):
                score -= 8
            out.append((score, c))
    out.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, c in out]


def main():
    limit, stage = 0, None
    for i, a in enumerate(sys.argv):
        if a == '--limit':
            limit = int(sys.argv[i + 1])
        if a == '--stage':
            stage = sys.argv[i + 1]

    ensure_dict()
    table = load_t2s()
    poems = V.load_poems()
    if stage:
        poems = [p for p in poems if p.get('stage') == stage]
    if limit:
        poems = poems[:limit]

    results = []
    stats = {'attested': 0, 'partial': 0, 'notfound': 0, 'nosource': 0}
    for n, p in enumerate(poems, 1):
        title = p['title']
        author = p.get('author') or ''
        lines = [M.strip_punct(x) for x in (p.get('lines') or [])]
        lines = [x for x in lines if x]
        rec = {'id': p['id'], 'title': title, 'author': author, 'stage': p.get('stage'),
               'page': None, 'url': None, 'lines': len(lines), 'hit': 0,
               'miss': [], 'variantNotes': []}
        try:
            best = None
            for cand in candidates(title, author, p.get('dynasty'), table)[:3]:
                real, raw = page_text(cand)
                txt, notes = clean(raw, table)
                if '消歧义' in txt[:400] or '重定向' in txt[:40]:
                    continue
                hit = sum(1 for ln in lines if ln and line_in(ln, txt))
                if best is None or hit > best['hit']:
                    best = {'page': real, 'hit': hit, 'notes': notes, 'len': len(txt), 'txt': txt}
                if hit == len(lines):
                    break
                time.sleep(0.10)
            if best:
                rec['page'] = best['page']
                rec['url'] = 'https://zh.wikisource.org/wiki/' + urllib.parse.quote(best['page'])
                rec['hit'] = best['hit']
                rec['variantNotes'] = best['notes'][:12]
                src_txt = best['txt']
                rec['miss'] = []
                for ln in lines:
                    if not ln or line_in(ln, src_txt):
                        continue
                    near = nearest(ln, src_txt)
                    rec['miss'].append({'line': ln, 'nearest': near})
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
            rec['page'] or '找不到来源页'))
        time.sleep(0.10)

    OUT.write_text(json.dumps({
        'note': '每篇原文的独立出处核对结果。来源：维基文库 zh.wikisource.org（公有领域文本）。'
                '繁体转简体用 OpenCC TSCharacters 字表（Apache-2.0），只用于比对，不改仓内正文。'
                'variantNotes 是页面里的「一作某」夹注，是异文线索，不是错误。',
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
