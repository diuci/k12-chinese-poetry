#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把核对用的来源正文缓存下来，供校勘时直接对照，不用一遍遍联网。

用法：
  python tools/fetch-source-excerpt.py            # 只缓存 data/text-sources.json 里点名过的篇目
  python tools/fetch-source-excerpt.py --all      # 全仓都缓存
产出：data/source-excerpts.json
"""
import json
import sys
import time
import urllib.parse
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import match as M  # noqa: E402
import validate as V  # noqa: E402
import importlib.util

spec = importlib.util.spec_from_file_location('cts', str(ROOT / 'tools' / 'check-text-sources.py'))
cts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cts)

SRC = ROOT / 'data' / 'text-sources.json'
OUT = ROOT / 'data' / 'source-excerpts.json'


def main():
    want_all = '--all' in sys.argv
    if not SRC.exists():
        print('先跑 python tools/check-text-sources.py')
        return 1
    checked = {r['id']: r for r in json.loads(SRC.read_text(encoding='utf-8'))['results']}
    table = cts.load_t2s()
    poems = V.load_poems()
    out = {}
    for n, p in enumerate(poems, 1):
        rec = checked.get(p['id'])
        if not want_all and (rec is None or not rec.get('miss')):
            continue
        page = (rec or {}).get('page')
        if not page:
            continue
        try:
            real, raw = cts.page_text(page)
            txt, notes = cts.clean(raw, table)
        except Exception as exc:
            out[p['id']] = {'error': str(exc)}
            continue
        lines = [M.strip_punct(x) for x in (p.get('lines') or [])]
        lines = [x for x in lines if x]
        anchors = [txt.find(x) for x in lines if txt.find(x) >= 0]
        excerpt = txt
        if anchors:
            lo, hi = min(anchors), max(anchors)
            hi = min(len(txt), hi + max(len(x) for x in lines) + 40)
            excerpt = txt[max(0, lo - 40):hi]
        out[p['id']] = {
            'title': p['title'], 'author': p.get('author'), 'page': real,
            'url': 'https://zh.wikisource.org/wiki/' + urllib.parse.quote(real),
            'pageChars': len(txt), 'excerpt': excerpt, 'variantNotes': notes[:16],
        }
        print('[%3d] %s（%s） 缓存 %d 字  %s' % (n, p['title'], p.get('author'), len(excerpt), real))
        time.sleep(0.10)
    OUT.write_text(json.dumps({
        'note': '校勘对照用的来源正文缓存。来源：维基文库 zh.wikisource.org。'
                '繁体已按 OpenCC 单字表转成简体，仅用于对照。',
        'generated': time.strftime('%Y-%m-%d'), 'entries': out,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('已写 data/source-excerpts.json：%d 篇' % len(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
