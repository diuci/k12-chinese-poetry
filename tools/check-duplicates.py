# -*- coding: utf-8 -*-
"""查两类「不会报错但一定不对」的问题。

起因：小学五年级下册有一首《寒下曲》(卢纶)。卢纶根本没写过这首诗，
是《塞下曲》被写错了标题。诗人、诗句、联句跟四年级下册那首完全一样。

为什么一直没被发现：
- validate.py 校验的是「一首诗自身是否合规」，不校验「这一首是否真实存在」
- 站点构建照常生成页面，链接全通，死链 0
- 游戏照常取到诗，能玩

也就是说，它通过了所有现有检查。只有把「同一首诗出现两次」单独拎出来看，
才会发现其中一份的标题是错的。

检查项：
1. 诗文完全相同的条目——逐组列出，标题不同���最可疑
2. 标题看起来是错别字（与另一条同作者、同诗文的条目标题只差一个字）

用法：python tools/check-duplicates.py
"""
import json
import pathlib
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
if suspect:
    print('%s 标题不一致的组 %d，需人工确认哪一份的标题是对的：' % (bad, len(suspect)))
    for g in suspect:
        print('    %s' % '  vs  '.join('%s《%s》(%s)' % (x['author'], x['title'], x['author']) for x in g))
    sys.exit(1)
print('%s 没有标题不一致的重复' % ok)
