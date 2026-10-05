# -*- coding: utf-8 -*-
"""查三类「不会报错但一定不对」的问题。

起因：小学五年级下册有一首《寒下曲》(卢纶)。卢纶根本没写过这首诗，
是《塞下曲》被写错了标题。诗人、诗句、联句跟四年级下册那首完全一样。

为什么一直没被发现：
- validate.py 校验的是「一首诗自身是否合规」，不校验「这一首是否真实存在」
- 站点构建照常生成页面，链接全通，死链 0
- 游戏照常取到诗，能玩

也就是说，它通过了所有现有检查。只有把「同一首诗出现两次」单独拎出来看，
才会发现其中一份的标题是错的。

检查项：
1. 诗文完全相同的条目——逐组列出，标题不同的最可疑
2. **内容重叠**的条目：一方是另一方的子集（不同书目的节选），
   但作者/朝代标注不同——这能抓出「出处标错」的错误
3. 标题看起来是错别字（与另一条同作者、同诗文的条目标题只差一个字）

第 2 条的例子：八年级下册的《杂说》标着「韩愈·唐」，
可它的四句全是《礼记·学记》里的句子，与同册的《虽有嘉肴》
（已正确标为佚名·先秦）逐句重合。作者标错，正是靠这条抓出来的。

用法：python tools/check-duplicates.py
"""
import json
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'poems.json'

sys.path.insert(0, str(ROOT / 'tools'))
try:
    from common import C
    ok, bad, warn = C.OK, C.BAD, C.WARN
except Exception:
    ok, bad, warn = '[ok]', '[!!]', '[--]'

# 已人工确认的合法异名。不是错别字，是同一段文字在不同教材里的两个名字，
# 故意留两个条目（各归各册），不再报警。
KNOWN_ALIASES = {
    frozenset(['大道之行也', '礼运']): '同一段《礼记·礼运》选文，篇名与通称并存',
}

poems = json.loads(DATA.read_text(encoding='utf-8'))['poems']
by_text = defaultdict(list)
for p in poems:
    by_text[''.join(p.get('lines') or [])].append(p)

print('=== 重复诗文检查 ===')
print('总篇数 %d，唯一诗文 %d' % (len(poems), len(by_text)))
print('')

suspect = []
for text, group in by_text.items():
    if len(group) < 2:
        continue
    titles = [g['title'] for g in group]
    same_title = len(set(titles)) == 1
    print('%s %d 首同诗：%s' % (
        warn if same_title else bad,
        len(group),
        '  |  '.join('%s《%s》%s' % (g['id'], g['title'], g['volume']) for g in group)))
    if not same_title:
        key = frozenset(titles)
        if key in KNOWN_ALIASES:
            print('       %s 已登记为合法异名：%s' % (ok, KNOWN_ALIASES[key]))
        else:
            suspect.append(group)

print('')

# ---- 内容重叠：一方是另一方的子集，但作者/朝代标注不一致 ----
# 不同条目的「必背名句」可以取自同一段原文的不同位置，这是正常的。
# 但如果两边作者或朝代标得不一样，就至少有一边标错了。
print('内容重叠检查（取自同一段原文的不同位置）')
# 必须按**整行**比对，不能把整段 CJK 连成一大串再找子串：
# 不同条目的必背名句取自同一段原文的不同位置，整串拼接后彼此根本不会命中，
# 检查会「零重叠」地空过——比没有检查更危险。
line_sets = {}
for p in poems:
    lines = p.get('linesPunct') or []
    line_sets[p['id']] = set(
        re.sub(r'[^\u4e00-\u9fff]', '', ln) for ln in lines
        if len(re.sub(r'[^\u4e00-\u9fff]', '', ln)) >= 4
    )
overlap_bad = []
n_pairs = 0
seen_pairs = set()
for i, a_ in enumerate(poems):
    for b_ in poems[i + 1:]:
        la, lb = line_sets[a_['id']], line_sets[b_['id']]
        if not la or not lb:
            continue
        inter = la & lb
        if len(inter) < 2:
            continue
        pair = tuple(sorted([a_['id'], b_['id']]))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        n_pairs += 1
        same_src = (a_['author'] == b_['author'] and a_['dynasty'] == b_['dynasty'])
        if not same_src:
            overlap_bad.append((a_, b_, len(inter)))
            print('   %s %s《%s》(%s·%s)  vs  %s《%s》(%s·%s)  重合 %d 句'
                  % (bad, a_['id'], a_['title'], a_['author'], a_['dynasty'],
                     b_['id'], b_['title'], b_['author'], b_['dynasty'], len(inter)))
print('   检出内容重叠的条目对: %d' % n_pairs)
if n_pairs == 0:
    print('   %s 一处重叠都没有——很可能是比对方式写错了，不是诗库真这么干净' % warn)
print('')
if overlap_bad:
    print('%s 有 %d 处作者/朝代标注与内容出处对不上，需人工确认' % (bad, len(overlap_bad)))
else:
    print('%s 没有发现出处标注冲突' % ok)

print('')
if suspect or overlap_bad:
    print('%s 标题不一致的组 %d，需人工确认哪一份的标题是对的：' % (bad, len(suspect)))
    for g in suspect:
        print('    %s' % '  vs  '.join('%s《%s》(%s)' % (x['author'], x['title'], x['author']) for x in g))
    sys.exit(1)
print('%s 没有标题不一致的重复' % ok)
