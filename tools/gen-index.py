#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 poems/索引.md —— 主题/体裁/朝代三维交叉索引。

索引从 data/poems.json 生成，因此永远与实际内容一致。
用法：python tools/gen-index.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'poems.json'
OUT = ROOT / 'poems' / '索引.md'


def die(msg):
    print('[index] ERROR: ' + msg, file=sys.stderr)
    sys.exit(1)


def main():
    if not DATA.exists():
        die('缺少 data/poems.json，请先跑 python tools/build.py')

    d = json.loads(DATA.read_text(encoding='utf-8'))
    poems = d['poems']

    by_theme = defaultdict(list)
    by_form = defaultdict(list)
    by_dyn = defaultdict(list)
    by_stage = defaultdict(list)

    for p in poems:
        # 以前这一行把全部 252 篇都塞进「小学N年级」：初中被写成小学7/8/9年级，
        # 高中全落进「小学None年级」。学段必须从 stage 来，年级只是学段内的细分。
        stage = p.get('stage') or '未分学段'
        grade = p.get('grade')
        if stage in ('小学', '初中') and grade:
            by_stage['%s%d年级' % (stage, int(grade))].append(p)
        else:
            by_stage[stage].append(p)
        for t in p.get('theme') or ['未分类']:
            by_theme[t].append(p)
        by_form[p.get('form') or '未标注'].append(p)
        by_dyn[p.get('dynasty') or '未标注'].append(p)

    # 护栏：分组名里出现 None / ? 就是上面那个 bug 的复发信号，不许生成这种导航页。
    bad = [k for k in by_stage if 'None' in k or '?' in k]
    if bad:
        print('[gen-index] 分组名坏了：%s —— 学段/年级字段没接对，拒绝生成' % '、'.join(bad))
        raise SystemExit(1)

    L = []
    L.append('# 篇目索引\n')
    L.append('> 本文件由 `tools/gen-index.py` 从 `data/poems.json` 自动生成，'
             '请勿手改。\n')
    L.append('共 **%d 篇**。\n' % len(poems))

    # ---- 学段
    L.append('\n## 按学段\n')
    order = {'小学': 0, '初中': 1, '高中': 2}
    for stage in sorted(by_stage, key=lambda s: (order.get(s[:2], 9), s)):
        L.append('\n### %s（%d 篇）\n' % (stage, len(by_stage[stage])))
        for p in sorted(by_stage[stage], key=lambda x: x['title']):
            L.append('- [%s](%s/%s.md) —— %s · %s'
                     % (p['title'], p.get('volume', ''), p['title'],
                        p['author'], p['dynasty']))

    # ---- 主题
    L.append('\n## 按主题\n')
    for t in sorted(by_theme, key=lambda x: (-len(by_theme[x]), x)):
        ps = by_theme[t]
        if len(ps) < 2:
            continue                      # 只有 1 篇的主题不单列，避免噪声
        L.append('\n### %s（%d 篇）\n' % (t, len(ps)))
        L.append(' '.join('[%s](%s/%s.md)'
                         % (p['title'], p.get('volume', ''), p['title'])
                         for p in sorted(ps, key=lambda x: x['title'])))

    # ---- 体裁
    L.append('\n## 按体裁\n')
    for f in sorted(by_form, key=lambda x: (-len(by_form[x]), x)):
        ps = by_form[f]
        L.append('\n- **%s**（%d 篇）：%s'
                 % (f, len(ps),
                    ' '.join(p['title'] for p in
                             sorted(ps, key=lambda x: x['title']))))

    # ---- 朝代
    L.append('\n## 按朝代\n')
    for dyn in sorted(by_dyn, key=lambda x: (-len(by_dyn[x]), x)):
        ps = by_dyn[dyn]
        L.append('\n- **%s**（%d 篇）：%s'
                 % (dyn, len(ps),
                    ' '.join(p['title'] for p in
                             sorted(ps, key=lambda x: x['title']))))

    # ---- 高频篇目（中考）
    hi = sorted([p for p in poems if (p.get('examFreq') or 0) >= 0.85],
                key=lambda x: -(x.get('examFreq') or 0))
    if hi:
        L.append('\n## 中考高频（exam_freq ≥ 0.85）\n')
        L.append(' '.join('[%s](%s/%s.md)'
                         % (p['title'], p.get('volume', ''), p['title'])
                         for p in hi))

    OUT.write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('[index] 写出 %s（%d 篇，主题 %d 个）'
          % (OUT.relative_to(ROOT), len(poems), len(by_theme)))


if __name__ == '__main__':
    main()