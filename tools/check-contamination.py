# -*- coding: utf-8 -*-
"""列出「本篇内容与别的篇目重叠」的情况，供人工判断。

起因：高中选修的《黄冈竹楼记》站点上显示的是

    ## 必背名句
    万里赴戎机。

    黄州居士，谪居之。

「万里赴戎机」是《木兰辞》的句子。一整页的诗，作者写着王禹偁，
读者看到的却是木兰。构建通过、校验通过、链接全通、注音齐全。

## 为什么这个工具只 warn，不 exit 1

试过两版硬判据，都不成立：

**第一版**：整篇句子被另一篇完全包含。
→ 漏报（这里只有一句是外来的），误报 11 处合法重复。

**第二版**：外来句占全篇一半就报。
→ 误报 9 处。因为库里大量是同一原文的不同选段
  （庄子一则 / 北冥有鱼 / 逍遥游都出自《逍遥游》；
   礼记一则 / 虽有嘉肴 / 杂说都出自《学记》），
  也有跨作者化用——宋濂《送东阳马生序》引韩愈《师说》，这些是语文课会讲的写法。

  ⚠️ 这里原先举的「陆游《示儿》原句引王安石《桂枝香》」是**错的**：那不是化用，
  是《桂枝香》的篇目文件里混进了《示儿》的结尾两句，注释、译文、赏析全建在这两句上。
  2026-10-07 查出并整篇重写，见该篇「旧文本裁定」。例子留着当反面教材：
  「看起来像化用」不等于「是化用」，每一处被点名的重叠都要逐对裁定。

关键问题：**「半个字面来自他作」这件事，本身不足以判定串篇。**
陆游引王安石和张冠李戴，在数据上长得一模一样。
所以这里只负责把重叠摆出来，不替人下结论。

每一处被点名的重叠都要在 data/overlap-verdicts.json 里有一条裁定；没有裁定且重叠过半即 exit 1。
裁定表里的键若对不上当前检出的重叠（篇目改名或删了），工具会报「裁定过期」。

旧版说明（保留）：需要人工核的曾有一处《黄冈竹楼记》，它整页只有两句，
其中一句是《木兰辞》的名句，而另一句「黄州居士，谪居之」
是否为该文原句，需要拿纸本校对——离线无法确认，故不改写。

用法：
    python tools/check-contamination.py          # 列清单，人工过
    python tools/check-contamination.py --selftest
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'poems.json'
ok, warn = '[ok]', '[--]'

SPLIT = re.compile(r'[\u3002\uff01\uff1f\uff1b\uff0c]')
MIN_LINES = 3


def lines_of(p):
    out = set()
    for ln in p.get('linesPunct') or []:
        for part in SPLIT.split(ln):
            t = re.sub(r'[^\u4e00-\u9fff]', '', part)
            if len(t) >= MIN_LINES:
                out.add(t)
    return out


def analyse(poems):
    lines = {p['id']: lines_of(p) for p in poems}
    owners = {}
    for p in poems:
        for ln in lines[p['id']]:
            owners.setdefault(ln, set()).add(p.get('author'))

    recs = []
    for p in poems:
        mine = lines[p['id']]
        if not mine:
            continue
        foreign = {ln for ln in mine
                   if owners[ln] and owners[ln] != {p.get('author')}}
        if not foreign:
            continue
        best, best_n = None, 0
        for q in poems:
            if q['id'] == p['id'] or q.get('author') == p.get('author'):
                continue
            n = len(foreign & lines[q['id']])
            if n > best_n:
                best, best_n = q, n
        if best is not None:
            recs.append((p, best, best_n, len(mine)))
    recs.sort(key=lambda r: -r[2] / r[3])
    return recs


if '--selftest' in sys.argv:
    print('=== 自测 ===')
    base = [
        # 同源选段：同作者、不同标题、内容相同
        {'id': 'z1', 'title': '庄子一则', 'author': '庄子',
         'linesPunct': ['北冥有鱼，其名为鲲。', '鲲之大不知其几千里也。']},
        {'id': 'z2', 'title': '逍遥游', 'author': '庄子',
         'linesPunct': ['北冥有鱼，其名为鲲。', '鲲之大不知其几千里也。']},
        # 化用：跨作者、引一句
        {'id': 's', 'title': '师说', 'author': '韩愈',
         'linesPunct': ['是故无贵无贱，无长无少。', '道之所存师之所存也。']},
        {'id': 'm2', 'title': '送东阳马生序', 'author': '宋濂',
         'linesPunct': ['是故无贵无贱，无长无少。', '余幼时即嗜学。', '求全责备。']},
        # 疑似串篇：他作名句占了整页的一句
        {'id': 'ml', 'title': '木兰辞', 'author': '佚名',
         'linesPunct': ['万里赴戎机，关山度若飞。']},
        {'id': 'a', 'title': '黄冈竹楼记', 'author': '王禹偁',
         'linesPunct': ['万里赴戎机。', '黄州居士谪居之。']},
    ]
    recs = analyse(base)
    got = {(r[0]['title'], r[1]['title']) for r in recs}
    r1 = ('黄冈竹楼记', '木兰辞') in got
    r2 = not {('庄子一则', '逍遥游'), ('逍遥游', '庄子一则')} & got
    r3 = ('送东阳马生序', '师说') in got
    print('%s 列出黄冈竹楼记→木兰辞: %s' % (ok if r1 else '[!!]', r1))
    print('%s 同作者选段不列入: %s' % (ok if r2 else '[!!]', r2))
    print('%s 化用也列出来（让人自己判断）: %s' % (ok if r3 else '[!!]', r3))
    sys.exit(0 if (r1 and r2 and r3) else 1)

poems = json.loads(DATA.read_text(encoding='utf-8'))['poems']
recs = analyse(poems)

VERD_PATH = ROOT / 'data' / 'overlap-verdicts.json'
verdicts = {}
if VERD_PATH.exists():
    verdicts = {v['pair']: v for v in json.loads(VERD_PATH.read_text(encoding='utf-8')).get('verdicts', [])}
seen, unadjudicated = set(), []
for p, q, n, tot in recs:
    key = '|'.join(sorted([p['id'], q['id']]))
    if key in verdicts:
        seen.add(key)
    elif n / tot >= 0.5:
        unadjudicated.append('%s《%s》↔ %s《%s》：%d/%d 句重叠，没有裁定' % (p['id'], p['title'], q['id'], q['title'], n, tot))
stale = sorted(k for k in verdicts if k not in seen)

print('=== 跨作者内容重叠（需人工确认，非报错） ===')
print('篇数 %d' % len(poems))
print('')
if recs:
    for p, q, n, tot in recs:
        flag = '  <<< 疑似串篇，需核对' if n / tot >= 0.5 else ''
        print('%s %s 《%s》（%s）：%d/%d 句见于《%s》（%s）%s'
              % (warn, p['id'], p['title'], p['author'], n, tot,
                 q['title'], q['author'], flag))
    print('')
    print('%s 共 %d 处，其中已裁定 %d 处（见 data/overlap-verdicts.json）。' % (warn, len(recs), len(seen)))
    for v in verdicts.values():
        if v['pair'] in seen:
            print('    [裁定] %s → %s：%s' % (v['pair'], v['verdict'], v['reason']))
else:
    print('%s 没有跨作者重叠' % ok)

if unadjudicated:
    print('')
    print('[!!] 有 %d 处重叠比例过半却没有裁定：' % len(unadjudicated))
    for x in unadjudicated:
        print('    ' + x)
if stale:
    print('')
    print('[!!] 裁定过期：data/overlap-verdicts.json 里这些键对不上当前检出的重叠，必须删或改：')
    for x in stale:
        print('    ' + x)
if unadjudicated or stale:
    sys.exit(1)
