#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教材用字核对：仓内正文，和统编教材课文里的字句，一不一样。

为什么必须有这一步：v1 冻结时承认的最大缺口就是「统编教材用字尚未逐本核对」。
公有领域底本（维基文库）这条腿站得稳，教材本那条腿还没接上。
而我们的口径是「教材版为准 + 附异文清单」——口径定了，却没工具去执行它。

来源地位必须说清楚：统编教材是版权作品。本工具**只取课文原文的字句**作为
「教材这里写作某字」的证据；教材的注释、译文、赏析一个字都不许进仓。
缓存文件只存在 data/textbook-cache/（已 gitignore 的话也不外传）。

用法：
  python tools/check-textbook.py                 # 全仓
  python tools/check-textbook.py --stage 高中    # 先做考试暴露面最大的一批
  python tools/check-textbook.py --limit 20
  python tools/check-textbook.py --refresh       # 忽略缓存重抓
"""
import difflib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import validate as V  # noqa: E402

BASE = 'https://yw.suyang123.com'
UA = {'User-Agent': 'diuci-content-check/1.0 (contact: hi@diuci.com)'}
OUT = ROOT / 'data' / 'textbook-attestations.json'
CACHE = ROOT / 'data' / 'textbook-cache'

# 仓内册次 → 教材课文目录页
VOLUMES = {
    '一年级上册': '/xiaoxue/yinianji/shangce.html',
    '一年级下册': '/xiaoxue/yinianji/xiace.html',
    '二年级上册': '/xiaoxue/ernianji/shangce.html',
    '二年级下册': '/xiaoxue/ernianji/xiace.html',
    '三年级上册': '/xiaoxue/sannianji/shangce.html',
    '三年级下册': '/xiaoxue/sannianji/xiace.html',
    '四年级上册': '/xiaoxue/sinianji/shangce.html',
    '四年级下册': '/xiaoxue/sinianji/xiace.html',
    '五年级上册': '/xiaoxue/wunianji/shangce.html',
    '五年级下册': '/xiaoxue/wunianji/xiace.html',
    '六年级上册': '/xiaoxue/liunianji/shangce.html',
    '六年级下册': '/xiaoxue/liunianji/xiace.html',
    '七年级上册': '/chuzhong/qinianji/shangce.html',
    '七年级下册': '/chuzhong/qinianji/xiace.html',
    '八年级上册': '/chuzhong/banianji/shangce.html',
    '八年级下册': '/chuzhong/banianji/xiace.html',
    '九年级上册': '/chuzhong/jiunianji/shangce.html',
    '九年级下册': '/chuzhong/jiunianji/xiace.html',
    '必修上册': '/gaozhong/bixiushang.html',
    '必修下册': '/gaozhong/bixiuxia.html',
    '选择性必修上册': '/gaozhong/xuanxiushang.html',
    '选择性必修中册': '/gaozhong/xuanxiuzhong.html',
    '选择性必修下册': '/gaozhong/xuanxiuxia.html',
}
# 课标指定选修、统编教材课本里没有的篇目所在目录：不是错误，是「教材里没有这篇」
NO_TEXTBOOK_VOLUME = '选修（2026起默写）'

TEXT_WRAP = re.compile(r'<p class="text-wrap[^"]*"[^>]*>([\s\S]*?)</p>')
TAG = re.compile(r'<[^>]+>')
PUNCT = re.compile(r'[^一-鿿]')
# 目录页有两种写法：锚文本在 > 之后（可能换行缩进），也可能只在 title="…课文朗读" 属性里。
# 只认锚文本会漏掉整批课文——漏了就会把「工具没抓到」误报成「教材里没有这篇」。
TITLE_ATTR = re.compile(r'href="(/[^"]+?_langdu\.html)"[^>]*?title="([^"]{1,60}?)课文朗读"')
TITLE_LINE = re.compile(r'href="(/[^"]+?_langdu\.html)"[^>]*>([\s\S]{1,80}?)</a>')


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def cached(url, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = re.sub(r'[^0-9A-Za-z]', '_', url)[:-4] + '.html'
    p = CACHE / key
    if p.exists() and not refresh:
        return p.read_text(encoding='utf-8')
    html = fetch(url)
    p.write_text(html, encoding='utf-8')
    time.sleep(0.4)
    return html


def strip_tags(html):
    return TAG.sub(' ', html)


def norm(s):
    return PUNCT.sub('', s or '')


def volume_index(path, refresh=False):
    """一册的课文目录：[(课文名, 课文页 URL)]。"""
    html = cached(BASE + path, refresh)
    out, seen = [], set()
    for rx in (TITLE_ATTR, TITLE_LINE):
        for m in rx.finditer(html):
            url, name = m.group(1), strip_tags(m.group(2)).strip()
            if url in seen or not name:
                continue
            seen.add(url)
            out.append((name, BASE + url))
    return out


def lesson_text(url, refresh=False):
    """课文页里的原文段落（只取 audioModule 里的 text-wrap，不碰译文注释）。"""
    html = cached(url, refresh)
    i = html.find('audioModule play-box')
    if i < 0:
        i = 0
    j = html.find('details-box', i)
    seg = html[i:j if j > i else len(html)]
    paras = [strip_tags(x).strip() for x in TEXT_WRAP.findall(seg)]
    return [p for p in paras if norm(p)]


def stage_of(volume):
    if volume in ('必修上册', '必修下册') or volume.startswith('选择性必修'):
        return '高中'
    if volume[:1] in '七八九':
        return '初中'
    return '小学'


def same_stage(a, b):
    return stage_of(a) == stage_of(b)


def title_candidates(title, subtitle):
    t = re.sub(r'[《》]', '', title or '')
    subs = [t]
    if subtitle:
        s = re.sub(r'[《》（）]', '', subtitle)
        subs += [t + s, t + ' ' + s]
    return [re.sub(r'\s+', '', x) for x in subs]


def match_lesson(poem, lessons):
    """按篇名在这一册的课文里找。副标题、带星号的自读课文、带编号都要能对上。"""
    cands = title_candidates(poem.get('title'), poem.get('subtitle'))
    for name, url in lessons:
        n = re.sub(r'^[\d.\-*（）\s]+', '', name)
        n = re.sub(r'[《》（）\s]', '', n)
        if not n:
            continue
        for c in cands:
            if n == c or (len(c) >= 3 and (c in n or n in c)):
                return name, url
    return None, None


def diff_against(line, book):
    """对不上的那句，教材那边到底写的是什么。

    只报「对不上」没有用——得指出差在哪个字，否则下一步只能靠猜。
    先找这句与教材正文的最长公共片段当锚，取锚附近同样长的窗口，再逐段对齐。
    """
    key = norm(line)
    if not key or not book:
        return []
    sm = difflib.SequenceMatcher(None, key, book, autojunk=False)
    m = sm.find_longest_match(0, len(key), 0, len(book))
    if m.size < 4:
        return [{'ours': key, 'textbook': None}]
    start = max(0, m.b - m.a)
    window = book[start:start + len(key) + 40]
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, key, window, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        out.append({'ours': key[i1:i2], 'textbook': window[j1:j2],
                    'context': window[max(0, j1 - 8):j2 + 8]})
    return out


def compare(poem, paras):
    """仓内每一句（名句 + 全文）去教材原文里找。"""
    book = norm(''.join(paras))
    ours = []
    for ln in (poem.get('linesPunct') or []):
        ours.append(('名句', ln))
    for ln in (poem.get('fullLinesPunct') or []):
        ours.append(('全文', ln))
    hit, miss = 0, []
    for kind, ln in ours:
        key = norm(ln)
        if len(key) < 4:
            continue
        if key in book:
            hit += 1
        else:
            miss.append({'kind': kind, 'line': ln.strip(), 'diff': diff_against(ln, book)})
    return hit, len(ours), miss


def main():
    refresh = '--refresh' in sys.argv
    stage = None
    if '--stage' in sys.argv:
        stage = sys.argv[sys.argv.index('--stage') + 1]
    limit = 0
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])

    poems = V.load_poems()
    if stage:
        poems = [p for p in poems if p.get('stage') == stage]
    ids = None
    if '--ids' in sys.argv:
        ids = set(sys.argv[sys.argv.index('--ids') + 1].split(','))
    if ids:
        poems = [p for p in poems if p['id'] in ids]
    if limit:
        poems = poems[:limit]

    indexes = {}
    results = []
    for p in poems:
        vol = (p.get('volume') or '').replace('课外诵读', '').strip()
        entry = {'id': p['id'], 'title': p['title'], 'author': p.get('author'),
                 'stage': p.get('stage'), 'volume': p.get('volume')}
        if p.get('volume') == NO_TEXTBOOK_VOLUME:
            entry.update(status='no-textbook',
                         note='课标指定选修篇目，统编教材课本未收（不是错误）')
            results.append(entry)
            print('[%d/%d] -- %s：教材不收（选修指定）' % (len(results), len(poems), p['title']))
            continue
        path = VOLUMES.get(vol)
        if not path:
            entry.update(status='unknown-volume', note='册次对不上教材目录：%s' % p.get('volume'))
            results.append(entry)
            print('[%d/%d] !! %s（%s）册次对不上' % (len(results), len(poems), p['title'], p.get('volume')))
            continue
        if path not in indexes:
            indexes[path] = volume_index(path, refresh)
        lessons = indexes[path]
        name, url = match_lesson(p, lessons)
        found_vol = vol
        if not url:
            # 仓内册次写错，和教材里真没有这篇，长得一模一样。必须分开：
            # 在同学段别的册里找一遍，找到就是「册次写错」，找不到才是「教材里没有」。
            for other_vol, other_path in VOLUMES.items():
                if same_stage(other_vol, vol) and other_path != path:
                    if other_path not in indexes:
                        indexes[other_path] = volume_index(other_path, refresh)
                    name, url = match_lesson(p, indexes[other_path])
                    if url:
                        found_vol = other_vol
                        break
        if not url:
            entry.update(status='lesson-not-found', volume_url=BASE + path,
                         note='同学段所有册的课文目录里都没有同名课文')
            results.append(entry)
            print('[%d/%d] !! %s（%s）教材里没有这篇' % (len(results), len(poems), p['title'], p.get('volume')))
            continue
        if found_vol != vol:
            entry.update(status='volume-mismatch', lesson=name, url=url,
                         declaredVolume=p.get('volume'), textbookVolume=found_vol)
            results.append(entry)
            print('[%d/%d] !! 册次写错：%s 仓内写「%s」，教材在「%s」' % (
                len(results), len(poems), p['title'], p.get('volume'), found_vol))
            continue
        paras = lesson_text(url, refresh)
        hit, total, miss = compare(p, paras)
        status = 'match' if (total and hit == total) else ('partial' if hit else 'mismatch')
        entry.update(status=status, lesson=name, url=url, hit=hit, total=total,
                     textbookParas=len(paras), miss=miss)
        results.append(entry)
        for mm in miss:
            d = mm['diff'] or [{'ours': norm(mm['line']), 'textbook': None}]
            for piece in d[:3]:
                print('      [%s] 仓内「%s」 → 教材「%s」' % (
                    mm['kind'], piece['ours'],
                    piece['textbook'] if piece['textbook'] else '找不到对应'))
        flag = 'ok' if status == 'match' else '!!'
        print('[%d/%d] %s %s（%s） %d/%d 句对上  %s' % (
            len(results), len(poems), flag, p['title'], p.get('volume'), hit, total, name))

    stats = {}
    for r in results:
        stats[r['status']] = stats.get(r['status'], 0) + 1
    OUT.write_text(json.dumps({'generated': time.strftime('%Y-%m-%d'),
                               'source': BASE,
                               'stats': stats, 'results': results},
                              ensure_ascii=False, indent=2), encoding='utf-8')
    print('')
    print('教材核对：%s' % ' / '.join('%s %d' % (k, v) for k, v in sorted(stats.items())))
    print('已写 data/textbook-attestations.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
