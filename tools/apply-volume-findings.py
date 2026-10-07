#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 data/volume-findings.json 的核对结论，把仓里的册次改成统编教材的实际册次。

只改三样东西：frontmatter 的 volume / grade，篇名下面那行「> 作者 · 朝代 · 体裁 · 学段 · 册次」，
以及文件所在的目录（目录名就是册次，站点按目录浏览）。
正文、注释、译文、赏析一个字不动——册次是元数据，不是文本。

默认空跑，只打印会改什么；加 --write 才动手。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / 'data' / 'volume-findings.json'
POEMS = ROOT / 'data' / 'poems.json'

GRADE_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def grade_of(volume):
    m = re.match(r'^([一二三四五六七八九])年级', volume or '')
    return GRADE_NUM[m.group(1)] if m else None


def new_volume(finding):
    """教材目录只证明「在哪一册」，不证明这一首是课内还是课外诵读。
    仓里原来带「课外诵读」后缀的，保留后缀——去掉它会把「课外古诗词诵读」这个位置信息丢掉。
    """
    vol = finding['textbookVolume']
    if finding['repoVolume'].endswith('课外诵读'):
        vol += '课外诵读'
    return vol


def patch_file(path, new_vol, new_grade, old_vol):
    text = path.read_text(encoding='utf-8')
    m = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    if not m:
        return None, 'frontmatter 读不出来'
    fm = m.group(1)
    fm2 = re.sub(r'^volume:\s*.*$', 'volume: %s' % new_vol, fm, count=1, flags=re.M)
    if new_grade is not None:
        fm2 = re.sub(r'^grade:\s*.*$', 'grade: %d' % new_grade, fm2, count=1, flags=re.M)
    if fm2 == fm:
        return None, 'frontmatter 没变化'
    out = '---\n' + fm2 + '\n---\n' + text[m.end():]
    # 篇名下面那行元信息：最后一个字段是册次
    out = re.sub(r'^>\s*([^\n]*?)·\s*' + re.escape(old_vol) + r'\s*$',
                 lambda mm: '> ' + mm.group(1).rstrip() + ' · ' + new_vol,
                 out, count=1, flags=re.M)
    return out, None


def main():
    write = '--write' in sys.argv
    data = json.loads(POEMS.read_text(encoding='utf-8'))['poems']
    by_id = {p['id']: p for p in data}
    f = json.loads(FINDINGS.read_text(encoding='utf-8'))
    # 两种都要改：仓里册次写错的，和仓里写着「教材不收」、教材目录里却有这篇的。
    # 后者以前被审计直接跳过，假话就藏在里面。
    todo = [x for x in f['findings']
            if x['status'] in ('volume-mismatch', 'claimed-absent-but-present')]
    moved, skipped = [], []
    for x in todo:
        p = by_id.get(x['id'])
        if p is None:
            skipped.append((x['title'], 'poems.json 里没有这个 id'))
            continue
        old_path = ROOT / p['_path']
        if not old_path.exists():
            skipped.append((x['title'], '文件不存在：%s' % p['_path']))
            continue
        vol = new_volume(x)
        grade = grade_of(vol) if p.get('stage') in ('小学', '初中') else None
        new_path = old_path.parent.parent / vol / old_path.name
        if new_path == old_path and grade == p.get('grade'):
            skipped.append((x['title'], '其实不用改（册次同名）'))
            continue
        patched, err = patch_file(old_path, vol, grade, x['repoVolume'])
        if err:
            skipped.append((x['title'], err))
            continue
        moved.append((p['stage'], x['title'], x['repoVolume'], vol,
                      '%s → %s' % (p['_path'], new_path.relative_to(ROOT)),
                      x['textbookLesson'], '官方印证' if x.get('officiallyConfirmed') else ''))
        if write:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_text(patched, encoding='utf-8')
            old_path.unlink()
    print('册次改动：%d 篇%s' % (len(moved), '' if write else '（空跑，未写盘）'))
    for stage, title, old, new, path, lesson, conf in moved:
        print('  %-4s %-22s %-14s → %-16s %s %s' % (stage, title, old, new, path, conf))
    if skipped:
        print()
        print('跳过 %d 篇' % len(skipped))
        for t, why in skipped:
            print('  %-22s %s' % (t, why))
    return 0


if __name__ == '__main__':
    sys.exit(main())
