#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给每篇 frontmatter 写上 textbookStatus：这一篇统编教材到底收没收。

为什么要有这个字段：仓里 52 篇是「课标要求背、统编教材课本里没有这一课」，
3 篇是「教材里那篇同名的是另一首诗」。这两件事以前只写在 data/volume-findings.json 里，
篇目文件自己不说，站点也就没法告诉学生「这篇教材不教，但课标要背」。

取值只有三种：
  统编教材收录
  统编教材未收（课标要求）
  统编教材收的是同名另一篇

结论全部从 data/volume-findings.json 来，不许手写。默认空跑，--write 才写盘。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTED = '统编教材收录'
NOT_COLLECTED = '统编教材未收（课标要求）'
NAME_CLASH = '统编教材收的是同名另一篇'
ALLOWED = (COLLECTED, NOT_COLLECTED, NAME_CLASH)


def status_of(finding, volume):
    if volume == '选修（2026起默写）':
        return NOT_COLLECTED
    if finding is None:
        return None
    st = finding['status']
    if st in ('match', 'title-variant', 'claimed-absent-but-present'):
        return COLLECTED
    if st == 'title-collision':
        return NAME_CLASH
    if st == 'absent':
        return NOT_COLLECTED
    if st == 'volume-mismatch':
        return None
    return None


def main():
    write = '--write' in sys.argv
    poems = json.loads((ROOT / 'data' / 'poems.json').read_text(encoding='utf-8'))['poems']
    f = json.loads((ROOT / 'data' / 'volume-findings.json').read_text(encoding='utf-8'))
    # absent / title-collision 两类不在 findings 里，各自单列，这里要一并收进来。
    # 只读 findings 的话这 55 篇全被判成「判不出状态」，看着像工具坏了，其实是漏读了两张表。
    by_id = {x['id']: x for x in f['findings']}
    for x in f.get('absent', []):
        by_id[x['id']] = {'id': x['id'], 'status': 'absent'}
    for x in f.get('titleCollision', []):
        by_id[x['id']] = {'id': x['id'], 'status': 'title-collision'}
    plan, unknown = [], []
    for p in poems:
        st = status_of(by_id.get(p['id']), p.get('volume') or '')
        if st is None:
            unknown.append((p['title'], p.get('volume')))
            continue
        path = ROOT / p['_path']
        text = path.read_text(encoding='utf-8')
        m = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
        if not m:
            unknown.append((p['title'], 'frontmatter 读不出来'))
            continue
        fm = m.group(1)
        if re.search(r'^textbookStatus:', fm, re.M):
            fm2 = re.sub(r'^textbookStatus:.*$', 'textbookStatus: %s' % st, fm, count=1, flags=re.M)
        else:
            fm2 = fm + '\ntextbookStatus: %s' % st
        if fm2 == fm:
            continue
        plan.append((p['stage'], p['title'], st, path))
        if write:
            path.write_text('---\n' + fm2 + '\n---\n' + text[m.end():], encoding='utf-8')
    tally = {}
    for _s, _t, st, _p in plan:
        tally[st] = tally.get(st, 0) + 1
    print('要写 textbookStatus：%d 篇%s' % (len(plan), '' if write else '（空跑，未写盘）'))
    for k in ALLOWED:
        print('  %-24s %d' % (k, tally.get(k, 0)))
    if unknown:
        print()
        print('判不出状态 %d 篇（这些必须先查清楚，不许默认成任何一种）' % len(unknown))
        for t, v in unknown:
            print('  %-22s volume=%s' % (t, v))
    return 0


if __name__ == '__main__':
    sys.exit(main())
